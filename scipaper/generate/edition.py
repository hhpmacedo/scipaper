"""
Edition assembly from generated pieces.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime, timezone

from .writer import Piece
from ..curate.models import ScoredPaper

logger = logging.getLogger(__name__)


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

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)


@dataclass
class AssemblyConfig:
    """Configuration for edition assembly."""
    max_pieces: int = 5
    max_quick_takes: int = 5
    target_word_count: int = 5000


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

    return edition


async def generate_quick_take(
    paper: ScoredPaper,
    config: Optional[AssemblyConfig] = None
) -> QuickTake:
    """Generate a brief summary for a runner-up paper."""
    return _fallback_quick_take(paper)


def _fallback_quick_take(paper: ScoredPaper) -> QuickTake:
    """Generate a quick take from abstract without LLM."""
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
