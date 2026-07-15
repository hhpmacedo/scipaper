"""
Edition assembly from generated pieces.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime, timezone

import anthropic

from .writer import Piece
from ..config import get_config
from ..curate.models import ScoredPaper
from ..retry import api_retry

logger = logging.getLogger(__name__)


QUICK_TAKE_PROMPT = """Write a Quick Take for a Signal newsletter. Signal explains AI research to software engineers and PMs who use AI but don't read papers.

A Quick Take is ONE sentence (occasionally two) in this format:
[Brief context] — [specific finding or result with a concrete number if available].

Rules:
- Must include what the paper FOUND, not what it STUDIED.
- Never use abstract-level descriptions like "researchers explore X" or "this paper studies Y".
- Never use banned words: revolutionary, groundbreaking, breakthrough, game-changing.
- If the paper has a concrete number, include it.

BAD: "Traditional vision-language models struggle with contrastive fine-grained taxonomic reasoning."
GOOD: "Fine-grained image classification gets harder when categories share visual features — a new benchmark shows top models drop 34 percentage points compared to standard classification tests."

Paper Title: {title}
Paper Abstract: {abstract}

Return ONLY a JSON object:
{{"one_liner": "<your one-sentence quick take>"}}
"""


EDITOR_NOTE_PROMPT = """You are the editor of Signal, a weekly newsletter that explains AI research to software engineers and PMs who use AI daily but don't read papers.

Write a 60-100 word "Editor's Note" that opens this week's edition. It must:
- Find the genuine throughline across the pieces below (a shared tension, a theme, or a useful contrast) — do NOT just list them.
- Be the MOST accessible text in the issue: plain language, no jargon, no piece titles dumped in a row.
- Have a point of view — what this week means for someone building with or deciding on AI.
- Zero hype. No "revolutionary", "breakthrough", "game-changing". State things plainly.
- End with one sentence orienting the reader ("If you read one thing this week...").

This week's pieces (hook — signal block):
{pieces_block}

Return ONLY the note text, no preamble, no heading."""


@dataclass
class QuickTake:
    """Brief summary for runners-up papers."""
    paper_id: str
    title: str
    one_liner: str
    paper_url: str


@dataclass
class Edition:
    """A complete edition ready for publishing."""
    week: str  # ISO week: 2026-W10
    issue_number: int

    # Main pieces (3-5)
    pieces: List[Piece] = field(default_factory=list)

    # Brief mentions (2-5)
    quick_takes: List[QuickTake] = field(default_factory=list)

    # Metadata
    created_at: Optional[datetime] = None
    published_at: Optional[datetime] = None

    # Stats
    total_words: int = 0
    papers_considered: int = 0
    papers_rejected: int = 0

    # Machine-generated connective throughline shown at the top of the edition.
    editor_note: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)


@dataclass
class AssemblyConfig:
    """Configuration for edition assembly."""
    max_pieces: int = 5
    max_quick_takes: int = 5
    target_word_count: int = 5000


EDITION_WORD_BUDGET = 3000


def check_edition_length(edition: "Edition", budget: int = EDITION_WORD_BUDGET) -> bool:
    """
    Return True if the edition's total feature word count is within budget.

    Non-fatal: logs a warning (does not raise) when over budget. The edition
    still ships regardless of the result — this check must never block a
    publish.
    """
    total = sum(p.word_count for p in edition.pieces)
    if total > budget:
        logger.warning(
            f"Edition {edition.week} is {total} words (> {budget} budget); "
            f"tighten the longest pieces."
        )
        return False
    return True


async def assemble_edition(
    pieces: List[Piece],
    runners_up: List[ScoredPaper],
    week: str,
    issue_number: int,
    config: Optional[AssemblyConfig] = None
) -> Edition:
    """
    Assemble an edition from generated pieces.

    1. Order pieces by importance (lead first)
    2. Generate Quick Takes for runners-up
    3. Calculate stats
    4. Return complete Edition object
    """
    config = config or AssemblyConfig()

    # Sort pieces (assume first piece is lead, rest by order)
    ordered_pieces = pieces[:config.max_pieces]

    # Generate Quick Takes
    quick_takes = []
    for paper in runners_up[:config.max_quick_takes]:
        try:
            qt = await generate_quick_take(paper, config)
            quick_takes.append(qt)
        except Exception as e:
            logger.warning(f"Quick take failed for {paper.paper.arxiv_id}: {e}")
            # Use fallback quick take
            qt = _fallback_quick_take(paper)
            quick_takes.append(qt)

    # Calculate total words
    total_words = sum(p.word_count for p in ordered_pieces)

    edition = Edition(
        week=week,
        issue_number=issue_number,
        pieces=ordered_pieces,
        quick_takes=quick_takes,
        total_words=total_words,
    )

    logger.info(
        f"Assembled edition {week}: "
        f"{len(ordered_pieces)} pieces, "
        f"{len(quick_takes)} quick takes, "
        f"{total_words} words"
    )

    # Autonomous, degradable Editor's Note: never raises, returns None on
    # any failure so the edition still assembles and ships.
    edition.editor_note = await generate_editor_note(edition.pieces, config)

    # Non-fatal length check: logs a warning if over budget but never blocks
    # publishing.
    check_edition_length(edition)

    return edition


async def generate_quick_take(
    paper: ScoredPaper,
    config: Optional[AssemblyConfig] = None,
    llm_provider: str = "anthropic",
    llm_model: Optional[str] = None,
    anthropic_api_key: Optional[str] = None,
    openai_api_key: Optional[str] = None,
) -> QuickTake:
    """Generate a brief summary for a runner-up paper using LLM."""
    prompt = QUICK_TAKE_PROMPT.format(
        title=paper.paper.title,
        abstract=paper.paper.abstract[:1000],  # Cap abstract to avoid token waste
    )

    try:
        one_liner = await _llm_quick_take(
            prompt,
            provider=llm_provider,
            model=llm_model,
            anthropic_api_key=anthropic_api_key,
            openai_api_key=openai_api_key,
        )
        return QuickTake(
            paper_id=paper.paper.arxiv_id,
            title=paper.paper.title,
            one_liner=one_liner,
            paper_url=paper.paper.pdf_url or f"https://arxiv.org/abs/{paper.paper.arxiv_id}",
        )
    except Exception as e:
        logger.warning(f"LLM quick take failed for {paper.paper.arxiv_id}, using fallback: {e}")
        return _fallback_quick_take(paper)


@api_retry
async def _llm_quick_take(
    prompt: str,
    provider: str = "anthropic",
    model: Optional[str] = None,
    anthropic_api_key: Optional[str] = None,
    openai_api_key: Optional[str] = None,
) -> str:
    """Call LLM and return one_liner string."""
    if provider == "anthropic":
        import anthropic
        _model = model or "claude-haiku-4-5-20251001"
        client = anthropic.AsyncAnthropic(api_key=anthropic_api_key)
        response = await client.messages.create(
            model=_model,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
    elif provider == "openai":
        from openai import AsyncOpenAI
        _model = model or "gpt-4o-mini"
        client = AsyncOpenAI(api_key=openai_api_key)
        response = await client.chat.completions.create(
            model=_model,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.choices[0].message.content.strip()
    else:
        raise ValueError(f"Unknown provider: {provider}")

    # Extract JSON
    if "```" in text:
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            text = match.group(1)
    try:
        data = json.loads(text)
        return data["one_liner"]
    except (json.JSONDecodeError, KeyError):
        # If not JSON, treat entire response as the one-liner
        return text.strip('"').strip()


async def generate_editor_note(
    pieces: List[Piece],
    config: Optional[AssemblyConfig] = None,
) -> Optional[str]:
    """
    Generate the edition's Editor's Note throughline.

    Degradable: returns None on any failure (missing pieces, API error) so
    the edition still ships and the renderers fall back to per-piece bullets.
    This must never raise — it's part of the fully autonomous pipeline and
    cannot be allowed to block a publish.
    """
    config = config or AssemblyConfig()
    if not pieces:
        return None

    pieces_block = "\n".join(
        f"- {p.hook} — {(p.signal_block or '').strip()}" for p in pieces
    )
    prompt = EDITOR_NOTE_PROMPT.format(pieces_block=pieces_block)

    try:
        signal_config = get_config()
        client = anthropic.AsyncAnthropic(api_key=signal_config.anthropic_api_key)
        response = await client.messages.create(
            model=signal_config.llm_model,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        return text or None
    except Exception as e:
        logger.warning(f"Editor's Note generation failed ({e}); edition ships without it")
        return None


def _fallback_quick_take(paper: ScoredPaper) -> QuickTake:
    """Generate a quick take from abstract without LLM (fallback only)."""
    abstract = paper.paper.abstract
    # Take first sentence of abstract as one-liner
    first_sentence = abstract.split(". ")[0] + "." if abstract else paper.paper.title
    # Truncate to ~50 words
    words = first_sentence.split()
    if len(words) > 50:
        first_sentence = " ".join(words[:50]) + "..."

    return QuickTake(
        paper_id=paper.paper.arxiv_id,
        title=paper.paper.title,
        one_liner=first_sentence,
        paper_url=paper.paper.pdf_url or f"https://arxiv.org/abs/{paper.paper.arxiv_id}",
    )


def generate_edition_subject(edition: Edition) -> str:
    """
    Generate email subject line for the edition.

    Format: "Signal #{issue_number}: {lead_piece_hook}"
    """
    if edition.pieces:
        lead_hook = edition.pieces[0].hook[:50]
        if len(edition.pieces[0].hook) > 50:
            lead_hook = lead_hook.rsplit(' ', 1)[0] + '...'
        return f"Signal #{edition.issue_number}: {lead_hook}"

    return f"Signal #{edition.issue_number} — This Week in AI Research"
