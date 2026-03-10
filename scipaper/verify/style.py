"""
Style consistency checker against the Style Constitution.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

from ..generate.writer import Piece

logger = logging.getLogger(__name__)


# Words banned by the Style Constitution
BANNED_WORDS = [
    "revolutionary", "groundbreaking", "game-changing", "breakthrough",
    "incredible", "amazing", "obviously", "clearly", "utilize", "leverage",
    "novel",  # prefer "new"
]

# Words to avoid (flag but don't fail)
CAUTION_WORDS = [
    "very", "really", "actually", "basically", "state-of-the-art",
]

# Hook patterns that indicate a method description instead of a capability/finding
_HOOK_METHOD_PATTERNS = [
    r"^researchers (propose|present|introduce|develop|design)",
    r"^we (propose|present|introduce|develop|design)",
    r"^this paper (presents|introduces|proposes|describes)",
    r"^in this (paper|work|study)",
    r"^a (new |novel )?(method|approach|framework|system|model) (for|to)",
]


@dataclass
class StyleIssue:
    """A single style issue."""
    severity: str  # "error", "warning"
    issue_type: str
    location: str  # e.g., "paragraph 3"
    description: str
    suggestion: Optional[str] = None


@dataclass
class StyleReport:
    """Full style compliance report."""
    piece_id: str
    compliant: bool
    issues: List[StyleIssue] = field(default_factory=list)
    
    word_count: int = 0
    word_count_ok: bool = True
    
    has_hook: bool = True
    has_limitations: bool = True
    structure_ok: bool = True


@dataclass
class StyleConfig:
    """Style checking configuration."""
    min_words: int = 800
    max_words: int = 1000  # Hard cap per updated Style Constitution
    strict_mode: bool = False  # If True, warnings become errors


def check_banned_words(content: str) -> List[StyleIssue]:
    """Check for banned words from Style Constitution."""
    issues = []

    for word in BANNED_WORDS:
        matches = list(re.finditer(r'\b' + re.escape(word) + r'\b', content, re.IGNORECASE))
        for match in matches:
            idx = match.start()
            context = content[max(0, idx - 20):idx + len(word) + 20]
            issues.append(StyleIssue(
                severity="error",
                issue_type="banned_word",
                location=f"...{context}...",
                description=f"Banned word: '{word}'",
                suggestion=f"Remove or replace '{word}' with more measured language"
            ))

    for word in CAUTION_WORDS:
        matches = list(re.finditer(r'\b' + re.escape(word) + r'\b', content, re.IGNORECASE))
        for match in matches:
            idx = match.start()
            context = content[max(0, idx - 20):idx + len(word) + 20]
            issues.append(StyleIssue(
                severity="warning",
                issue_type="caution_word",
                location=f"...{context}...",
                description=f"Consider removing: '{word}'",
                suggestion=f"'{word}' often adds no value - consider removing"
            ))

    return issues


def check_structure(content: str) -> List[StyleIssue]:
    """Check that piece follows required structure."""
    issues = []
    
    required_sections = [
        ("The Problem", "problem"),
        ("What They Did", "approach"),
        ("The Results", "results"),
        ("Why It Matters", "implications"),
    ]
    
    for section_name, section_type in required_sections:
        # Look for section header
        if section_name not in content and f"## {section_name}" not in content:
            issues.append(StyleIssue(
                severity="error",
                issue_type="missing_section",
                location="structure",
                description=f"Missing required section: '{section_name}'",
                suggestion=f"Add a '{section_name}' section"
            ))
    
    return issues


def check_word_count(content: str, config: StyleConfig) -> tuple:
    """Check word count is within bounds."""
    words = len(content.split())
    ok = config.min_words <= words <= config.max_words
    return words, ok


def check_citations(content: str) -> List[StyleIssue]:
    """Check that claims have citations."""
    issues = []
    
    # Look for citation pattern
    citation_pattern = r'\[§[\d.]+\]|\[Abstract\]|\[Table\s+\d+\]|\[Figure\s+\d+\]'
    citations = re.findall(citation_pattern, content)
    
    if len(citations) < 3:
        issues.append(StyleIssue(
            severity="error",
            issue_type="insufficient_citations",
            location="throughout",
            description=f"Only {len(citations)} citations found (minimum 3)",
            suggestion="Add more citations to ground claims in the paper"
        ))
    
    return issues


def check_hook_form(hook: str) -> List[StyleIssue]:
    """Check that the hook states a capability or finding, not a method description."""
    issues = []
    hook_lower = hook.strip().lower()

    for pattern in _HOOK_METHOD_PATTERNS:
        if re.match(pattern, hook_lower):
            issues.append(StyleIssue(
                severity="error",
                issue_type="hook_method_description",
                location="hook",
                description="Hook describes a method, not a capability or finding.",
                suggestion=(
                    "Rewrite hook to answer: what can now be done that couldn't before, "
                    "or what assumption just got challenged? Lead with the result, not the approach."
                ),
            ))
            break

    return issues


def check_numbers_in_results(content: str) -> List[StyleIssue]:
    """Check that The Results section contains at least one specific performance number."""
    issues = []

    # Extract The Results section
    results_match = re.search(
        r'##\s*The Results\s*\n(.*?)(?=\n##|\Z)',
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if not results_match:
        return issues  # Missing section caught by check_structure

    results_text = results_match.group(1)

    # Look for numeric performance indicators: digits followed by %, x, or comparison context
    has_number = bool(re.search(
        r'\b\d+(?:\.\d+)?(?:\s*%|\s*x\b|\s*times\b|\s*accuracy|\s*points?)',
        results_text,
        re.IGNORECASE,
    ))
    # Also accept patterns like "87 out of 100" or "X vs Y" with numbers
    has_comparison = bool(re.search(
        r'\b\d+(?:\.\d+)?\b.{0,40}\bvs\.?\b.{0,40}\b\d+(?:\.\d+)?\b',
        results_text,
        re.IGNORECASE,
    ))

    if not has_number and not has_comparison:
        issues.append(StyleIssue(
            severity="error",
            issue_type="missing_performance_number",
            location="The Results",
            description=(
                "The Results section contains no specific performance number with interpretable context. "
                "Quoting the abstract ('reliable performance') is not reporting results."
            ),
            suggestion=(
                "Add at least one specific number with a baseline: "
                "e.g., '87% accuracy vs. 62% for the prior best method'. "
                "If the paper has no reportable numbers, flag this explicitly in the Results section."
            ),
        ))

    return issues


def check_signal_block(signal_block: str) -> List[StyleIssue]:
    """Check that the signal block is present and covers capability, maturity, and decision."""
    issues = []

    if not signal_block or not signal_block.strip():
        issues.append(StyleIssue(
            severity="error",
            issue_type="missing_signal_block",
            location="signal_block",
            description="Signal block is missing. Required for executive readers.",
            suggestion=(
                "Add a 2-3 sentence signal block covering: "
                "(a) what capability is emerging, "
                "(b) maturity level (lab / emerging / actionable), "
                "(c) what decision it informs for practitioners."
            ),
        ))
        return issues

    word_count = len(signal_block.split())
    if word_count < 20:
        issues.append(StyleIssue(
            severity="warning",
            issue_type="signal_block_too_short",
            location="signal_block",
            description=f"Signal block is only {word_count} words — likely missing maturity or decision framing.",
            suggestion="Expand to 2-3 sentences covering capability, maturity, and practitioner decision.",
        ))

    return issues


async def check_style_compliance(
    piece: Piece,
    config: Optional[StyleConfig] = None
) -> StyleReport:
    """
    Check a piece against the Style Constitution.
    
    Stage 3 of the content pipeline:
    1. Check for banned/caution words
    2. Verify required structure
    3. Check word count
    4. Verify citations present
    
    Returns StyleReport.
    """
    config = config or StyleConfig()
    
    issues = []

    # Run checks
    issues.extend(check_banned_words(piece.content))
    issues.extend(check_structure(piece.content))
    issues.extend(check_citations(piece.content))
    issues.extend(check_hook_form(piece.hook))
    issues.extend(check_numbers_in_results(piece.content))
    issues.extend(check_signal_block(piece.signal_block or ""))

    # Word count (hard cap now 1000)
    word_count, word_count_ok = check_word_count(piece.content, config)
    if not word_count_ok:
        issues.append(StyleIssue(
            severity="warning",
            issue_type="word_count",
            location="overall",
            description=f"Word count {word_count} outside target {config.min_words}-{config.max_words}",
            suggestion="Adjust length to target range"
        ))
    
    # Determine compliance
    errors = [i for i in issues if i.severity == "error"]
    compliant = len(errors) == 0
    
    if config.strict_mode:
        warnings = [i for i in issues if i.severity == "warning"]
        compliant = compliant and len(warnings) == 0
    
    report = StyleReport(
        piece_id=piece.paper_id,
        compliant=compliant,
        issues=issues,
        word_count=word_count,
        word_count_ok=word_count_ok,
    )
    
    logger.info(
        f"Style check for {piece.paper_id}: "
        f"{'PASS' if compliant else 'FAIL'} "
        f"({len(errors)} errors, {len(issues) - len(errors)} warnings)"
    )
    
    return report
