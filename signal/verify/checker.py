"""
Adversarial verification of generated content.
"""

import logging
from dataclasses import dataclass, field
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


@dataclass
class VerificationConfig:
    """Configuration for verification."""
    llm_model: str = "claude-3-5-sonnet-20241022"
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
    
    # TODO: Implement verification
    #
    # 1. Format prompts with piece and paper
    # 2. Call LLM
    # 3. Parse JSON response
    # 4. Build VerificationReport
    # 5. If needs_revision and retries remaining, attempt auto-fix
    
    logger.info(f"Verifying piece for {paper.arxiv_id}")
    raise NotImplementedError("Verification not yet implemented")


async def attempt_auto_fix(
    piece: Piece,
    issues: List[VerificationIssue]
) -> Piece:
    """
    Attempt to auto-fix minor and some major issues.
    
    Returns updated Piece.
    """
    fixable = [i for i in issues if i.severity != IssueSeverity.CRITICAL and i.suggested_fix]
    
    if not fixable:
        return piece
    
    # TODO: Implement auto-fix
    # Apply suggested fixes to piece content
    
    logger.info(f"Attempting to auto-fix {len(fixable)} issues")
    raise NotImplementedError("Auto-fix not yet implemented")
