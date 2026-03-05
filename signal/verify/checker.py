"""
Adversarial verification of generated content.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Literal, Optional
from enum import Enum

from ..generate.writer import Piece
from ..curate.models import Paper

logger = logging.getLogger(__name__)


class IssueSeverity(str, Enum):
    MINOR = "minor"      # Style issue, can auto-fix
    MAJOR = "major"      # Factual concern, needs review
    CRITICAL = "critical"  # Clear misrepresentation, must reject


class IssueType(str, Enum):
    UNSUPPORTED = "unsupported"      # Claim not in cited passage
    OVERSTATED = "overstated"        # Claim stronger than source
    MISREPRESENTED = "misrepresented"  # Claim contradicts source
    MISSING_CONTEXT = "missing_context"  # Important caveat omitted


@dataclass
class VerificationIssue:
    """A single verification issue."""
    severity: IssueSeverity
    issue_type: IssueType
    claim_text: str
    cited_passage: str
    explanation: str
    suggested_fix: Optional[str] = None


@dataclass
class VerificationReport:
    """Full verification report for a piece."""
    paper_id: str
    status: Literal["pass", "fail", "needs_revision"]

    claims_checked: int
    claims_verified: int
    claims_failed: int

    issues: List[VerificationIssue] = field(default_factory=list)

    # Metadata
    model_used: str = ""
    verified_at: str = ""

    @property
    def pass_rate(self) -> float:
        if self.claims_checked == 0:
            return 0.0
        return self.claims_verified / self.claims_checked

    def should_reject(self) -> bool:
        """Determine if piece should be rejected."""
        critical_count = sum(1 for i in self.issues if i.severity == IssueSeverity.CRITICAL)
        major_count = sum(1 for i in self.issues if i.severity == IssueSeverity.MAJOR)

        # Reject if any critical issues or 3+ major issues
        return critical_count > 0 or major_count >= 3


VERIFICATION_SYSTEM_PROMPT = """You are a fact-checker for Signal, an AI research newsletter.

Your job is to verify that each claim in a piece is accurately supported by the cited passage from the original paper.

For each claim + citation pair, determine:
1. Does the cited passage actually support this claim?
2. Is the claim overstated compared to the source?
3. Does the claim misrepresent or contradict the source?
4. Is important context missing that would change the meaning?

Be rigorous but fair. Academic writing often hedges more than journalism, so reasonable simplification is okay. But:
- Numbers must be accurate
- Comparative claims ("better than X") must be supported
- Causal claims need evidence
- Limitations mentioned in the paper should be reflected

For each issue found, provide:
- Severity: minor / major / critical
- Type: unsupported / overstated / misrepresented / missing_context
- The claim text
- The actual passage from the paper
- Why this is an issue
- Suggested fix (if minor or major)
"""


VERIFICATION_USER_PROMPT = """Verify this piece against the original paper.

PIECE:
{piece_content}

ORIGINAL PAPER:
{paper_full_text}

Check each cited claim. Respond with JSON:
{{
  "claims_checked": <number>,
  "claims_verified": <number>,
  "claims_failed": <number>,
  "issues": [
    {{
      "severity": "minor|major|critical",
      "type": "unsupported|overstated|misrepresented|missing_context",
      "claim_text": "...",
      "cited_passage": "...",
      "explanation": "...",
      "suggested_fix": "..." or null
    }}
  ],
  "overall_assessment": "..."
}}
"""


AUTO_FIX_PROMPT = """Fix the following issues in this piece. Apply the suggested fixes while maintaining the piece's flow and style.

PIECE:
{piece_content}

ISSUES TO FIX:
{issues_json}

Return the corrected piece content only. Keep all valid citations intact. Remove or fix claims that are unsupported.
"""


@dataclass
class VerificationConfig:
    """Configuration for verification."""
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-4-20250514"
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    max_retries: int = 2  # Retry with fixes before failing
    strict_mode: bool = False  # If True, any major issue = fail


async def verify_piece(
    piece: Piece,
    paper: Paper,
    config: Optional[VerificationConfig] = None
) -> VerificationReport:
    """
    Run adversarial verification on a generated piece.

    Stage 2 of the content pipeline:
    1. Extract claims and citations from piece
    2. Call LLM to verify each claim against source
    3. Aggregate issues into report
    4. Determine pass/fail status

    Returns VerificationReport.
    """
    config = config or VerificationConfig()

    if not paper.full_text:
        raise ValueError(f"Paper {paper.arxiv_id} has no full text.")

    logger.info(f"Verifying piece for {paper.arxiv_id}")

    prompt = VERIFICATION_USER_PROMPT.format(
        piece_content=piece.content,
        paper_full_text=paper.full_text[:15000],
    )

    try:
        if config.llm_provider == "anthropic":
            response_text = await _verify_with_anthropic(prompt, config)
        elif config.llm_provider == "openai":
            response_text = await _verify_with_openai(prompt, config)
        else:
            raise ValueError(f"Unknown LLM provider: {config.llm_provider}")

        report = _parse_verification_response(response_text, paper.arxiv_id, config.llm_model)

    except Exception as e:
        logger.warning(f"LLM verification failed, using heuristic: {e}")
        report = _heuristic_verification(piece, paper)

    logger.info(
        f"Verification for {paper.arxiv_id}: {report.status} "
        f"({report.claims_verified}/{report.claims_checked} verified)"
    )

    return report


async def _verify_with_anthropic(prompt: str, config: VerificationConfig) -> str:
    """Verify using Anthropic API."""
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)
    response = await client.messages.create(
        model=config.llm_model,
        max_tokens=3000,
        system=VERIFICATION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text


async def _verify_with_openai(prompt: str, config: VerificationConfig) -> str:
    """Verify using OpenAI API."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=config.openai_api_key)
    response = await client.chat.completions.create(
        model=config.llm_model,
        max_tokens=3000,
        messages=[
            {"role": "system", "content": VERIFICATION_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )

    return response.choices[0].message.content


def _parse_verification_response(
    text: str, paper_id: str, model: str
) -> VerificationReport:
    """Parse LLM verification response into a VerificationReport."""
    text = text.strip()

    # Extract JSON from markdown code blocks
    if "```" in text:
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            text = match.group(1)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object
        match = re.search(r'\{.*"claims_checked".*\}', text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                return _fallback_report(paper_id, model)
        else:
            return _fallback_report(paper_id, model)

    issues = []
    for issue_data in data.get("issues", []):
        try:
            issues.append(VerificationIssue(
                severity=IssueSeverity(issue_data.get("severity", "minor")),
                issue_type=IssueType(issue_data.get("type", "unsupported")),
                claim_text=issue_data.get("claim_text", ""),
                cited_passage=issue_data.get("cited_passage", ""),
                explanation=issue_data.get("explanation", ""),
                suggested_fix=issue_data.get("suggested_fix"),
            ))
        except (ValueError, KeyError) as e:
            logger.warning(f"Failed to parse issue: {e}")

    claims_checked = data.get("claims_checked", 0)
    claims_verified = data.get("claims_verified", 0)
    claims_failed = data.get("claims_failed", 0)

    report = VerificationReport(
        paper_id=paper_id,
        status="pass",
        claims_checked=claims_checked,
        claims_verified=claims_verified,
        claims_failed=claims_failed,
        issues=issues,
        model_used=model,
        verified_at=datetime.utcnow().isoformat(),
    )

    # Determine status
    if report.should_reject():
        report.status = "fail"
    elif issues:
        report.status = "needs_revision"
    else:
        report.status = "pass"

    return report


def _fallback_report(paper_id: str, model: str) -> VerificationReport:
    """Return a needs_revision report when parsing fails."""
    return VerificationReport(
        paper_id=paper_id,
        status="needs_revision",
        claims_checked=0,
        claims_verified=0,
        claims_failed=0,
        issues=[VerificationIssue(
            severity=IssueSeverity.MINOR,
            issue_type=IssueType.UNSUPPORTED,
            claim_text="",
            cited_passage="",
            explanation="Verification response could not be parsed",
            suggested_fix="Re-run verification",
        )],
        model_used=model,
        verified_at=datetime.utcnow().isoformat(),
    )


def _heuristic_verification(piece: Piece, paper: Paper) -> VerificationReport:
    """
    Basic heuristic verification when LLM is unavailable.
    Checks that citations reference existing sections in the paper.
    """
    from ..generate.writer import extract_citations, validate_citations

    citations = extract_citations(piece.content)
    invalid = validate_citations(citations, paper.full_text)

    claims_checked = len(citations)
    claims_failed = len(invalid)
    claims_verified = claims_checked - claims_failed

    issues = []
    for inv in invalid:
        issues.append(VerificationIssue(
            severity=IssueSeverity.MAJOR,
            issue_type=IssueType.UNSUPPORTED,
            claim_text=inv["claim"],
            cited_passage="",
            explanation=f"Citation [{inv['citation']}] not found in paper",
            suggested_fix=f"Remove or re-cite claim: {inv['claim'][:80]}",
        ))

    status = "pass"
    if len(issues) > 0:
        status = "needs_revision"
    if len([i for i in issues if i.severity == IssueSeverity.CRITICAL]) > 0:
        status = "fail"

    return VerificationReport(
        paper_id=piece.paper_id,
        status=status,
        claims_checked=claims_checked,
        claims_verified=claims_verified,
        claims_failed=claims_failed,
        issues=issues,
        model_used="heuristic",
        verified_at=datetime.utcnow().isoformat(),
    )


async def attempt_auto_fix(
    piece: Piece,
    issues: List[VerificationIssue],
    config: Optional[VerificationConfig] = None
) -> Piece:
    """
    Attempt to auto-fix minor and some major issues.

    Returns updated Piece with fixes applied.
    """
    config = config or VerificationConfig()

    fixable = [i for i in issues if i.severity != IssueSeverity.CRITICAL and i.suggested_fix]

    if not fixable:
        return piece

    logger.info(f"Attempting to auto-fix {len(fixable)} issues")

    # Try LLM-based fix
    try:
        issues_json = json.dumps([
            {
                "claim": i.claim_text,
                "issue": i.explanation,
                "fix": i.suggested_fix,
            }
            for i in fixable
        ], indent=2)

        prompt = AUTO_FIX_PROMPT.format(
            piece_content=piece.content,
            issues_json=issues_json,
        )

        if config.llm_provider == "anthropic":
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)
            response = await client.messages.create(
                model=config.llm_model,
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            )
            fixed_content = response.content[0].text
        elif config.llm_provider == "openai":
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=config.openai_api_key)
            response = await client.chat.completions.create(
                model=config.llm_model,
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            )
            fixed_content = response.choices[0].message.content
        else:
            return piece

        piece.content = fixed_content
        piece.word_count = len(fixed_content.split())
        from ..generate.writer import extract_citations
        piece.citations = extract_citations(fixed_content)

        logger.info(f"Auto-fix applied: {piece.word_count} words, {len(piece.citations)} citations")
        return piece

    except Exception as e:
        logger.warning(f"Auto-fix failed, applying manual fixes: {e}")

    # Fallback: apply simple text replacements from suggested fixes
    content = piece.content
    for issue in fixable:
        if issue.claim_text and issue.suggested_fix:
            # Only replace if the claim text is found verbatim
            if issue.claim_text in content:
                content = content.replace(issue.claim_text, issue.suggested_fix, 1)

    piece.content = content
    piece.word_count = len(content.split())
    from ..generate.writer import extract_citations
    piece.citations = extract_citations(content)

    return piece
