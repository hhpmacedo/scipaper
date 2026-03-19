"""
Style consistency checker against the Style Constitution.

Uses a single LLM call per piece for reliable, context-aware checking.
Rule-based checks (banned words, word count) still run locally for speed.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

import anthropic

from ..generate.writer import Piece
from ..config import get_config

logger = logging.getLogger(__name__)


# Words banned by the Style Constitution — checked locally (fast, unambiguous)
BANNED_WORDS = [
    "revolutionary", "groundbreaking", "game-changing", "breakthrough",
    "incredible", "amazing", "obviously", "clearly", "utilize", "leverage",
    "novel",  # prefer "new"
]

# Words to avoid (flag but don't fail)
CAUTION_WORDS = [
    "very", "really", "actually", "basically", "state-of-the-art",
]

STYLE_CHECK_PROMPT = """\
You are a rigorous style editor for Signal, a weekly AI research newsletter. \
Your job is to check whether a drafted article meets the Style Constitution rules below.

## Style Constitution Rules

1. **Hook form** — The hook must lead with a capability, finding, or challenged assumption. \
It must NOT start with "Researchers propose/present/introduce", "We propose", "This paper presents", \
"In this paper", or "A new method for". The hook should answer: what can now be done that couldn't before?

2. **Quantified results** — The "## The Results" section must contain at least one specific, \
concrete finding. If the paper has benchmark numbers, they must be quoted with a baseline. \
If the paper has no benchmark numbers, the article must explicitly say so (e.g. "This paper \
reports no benchmark comparisons") and give a specific qualitative finding instead. \
Vague statements like "performs well", "substantially higher", "measurable fraction", or \
"achieves reliable performance" are NOT acceptable — they are paraphrases, not results. \
Only pass this check if the article either quotes real numbers OR explicitly acknowledges \
the absence of benchmarks with a reason.

3. **Signal block** — The signal_block field must be present, at least 20 words, and cover: \
(a) what capability is emerging, (b) maturity level (lab/emerging/actionable), \
(c) what decision it informs for practitioners.

4. **Required sections** — The article must contain all four sections: \
"## The Problem", "## What They Did", "## The Results", "## Why It Matters".

## Article to Check

**Hook:** {hook}

**Signal block:** {signal_block}

**Article content:**
{content}

## Instructions

Return a JSON object with this exact structure:
{{
  "issues": [
    {{
      "severity": "error" | "warning",
      "issue_type": "hook_method_description" | "missing_performance_number" | "missing_signal_block" | "signal_block_too_short" | "missing_section" | "other",
      "location": "<brief location description>",
      "description": "<what the issue is>",
      "suggestion": "<how to fix it>"
    }}
  ]
}}

Only include real issues. If the article is clean, return {{"issues": []}}.
Be strict on hook form and signal block. Be pragmatic on results numbers — \
if the paper genuinely has no quantifiable results (e.g. a theoretical or interpretability paper), \
do not flag it.
"""


@dataclass
class StyleIssue:
    """A single style issue."""
    severity: str  # "error", "warning"
    issue_type: str
    location: str
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
    max_words: int = 1000
    strict_mode: bool = False


def _check_banned_words(content: str) -> List[StyleIssue]:
    """Fast local check for banned and caution words."""
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
                suggestion=f"Replace '{word}' with more measured language",
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
                suggestion=f"'{word}' often adds no value",
            ))
    return issues


def _check_word_count(content: str, config: StyleConfig) -> tuple:
    words = len(content.split())
    ok = config.min_words <= words <= config.max_words
    return words, ok


async def check_style_compliance(
    piece: Piece,
    config: Optional[StyleConfig] = None,
) -> StyleReport:
    """
    Check a piece against the Style Constitution using an LLM call.

    Local checks (banned words, word count) run first for speed.
    All structural/semantic rules (hook form, results numbers, signal block,
    section presence) are delegated to a single Sonnet call.
    """
    config = config or StyleConfig()
    issues: List[StyleIssue] = []

    # --- Fast local checks ---
    issues.extend(_check_banned_words(piece.content))

    word_count, word_count_ok = _check_word_count(piece.content, config)
    if not word_count_ok:
        issues.append(StyleIssue(
            severity="warning",
            issue_type="word_count",
            location="overall",
            description=f"Word count {word_count} outside target {config.min_words}-{config.max_words}",
            suggestion="Adjust length to target range",
        ))

    # --- LLM structural check ---
    signal_config = get_config()
    client = anthropic.Anthropic(api_key=signal_config.anthropic_api_key)

    prompt = STYLE_CHECK_PROMPT.format(
        hook=piece.hook or "",
        signal_block=piece.signal_block or "",
        content=piece.content,
    )

    try:
        response = client.messages.create(
            model=signal_config.llm_model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        # Extract JSON object robustly — find first { ... } block
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in LLM response")
        data = json.loads(match.group())
        for item in data.get("issues", []):
            issues.append(StyleIssue(
                severity=item.get("severity", "warning"),
                issue_type=item.get("issue_type", "other"),
                location=item.get("location", "unknown"),
                description=item.get("description", ""),
                suggestion=item.get("suggestion"),
            ))
    except Exception as e:
        logger.warning(f"LLM style check failed for {piece.paper_id}: {e} — skipping structural checks")

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
    for issue in issues:
        logger.info(
            f"  [{issue.severity.upper()}] {issue.issue_type} @ {issue.location}: {issue.description}"
        )

    return report
