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
    max_words: int = 1200
    strict_mode: bool = False  # If True, warnings become errors


def check_banned_words(content: str) -> List[StyleIssue]:
    """Check for banned words from Style Constitution."""
    issues = []
    content_lower = content.lower()
    
    for word in BANNED_WORDS:
        if word in content_lower:
            # Find approximate location
            idx = content_lower.index(word)
            context = content[max(0, idx-20):idx+len(word)+20]
            
            issues.append(StyleIssue(
                severity="error",
                issue_type="banned_word",
                location=f"...{context}...",
                description=f"Banned word: '{word}'",
                suggestion=f"Remove or replace '{word}' with more measured language"
            ))
    
    for word in CAUTION_WORDS:
        if word in content_lower:
            idx = content_lower.index(word)
            context = content[max(0, idx-20):idx+len(word)+20]
            
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
    
    # Word count
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
