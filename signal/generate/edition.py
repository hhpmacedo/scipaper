"""
Edition assembly from generated pieces.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime

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
    week: str  # ISO week: 2025-W10
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
            self.created_at = datetime.utcnow()


@dataclass
class AssemblyConfig:
    """Configuration for edition assembly."""
    max_pieces: int = 5
    max_quick_takes: int = 5
    target_word_count: int = 5000  # Total edition


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
    
    # Sort pieces (assume first piece is lead, rest by score or order)
    ordered_pieces = pieces[:config.max_pieces]
    
    # Generate Quick Takes
    quick_takes = []
    for paper in runners_up[:config.max_quick_takes]:
        qt = await generate_quick_take(paper)
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


QUICK_TAKE_PROMPT = """Write a 1-2 sentence summary of this paper for a "Quick Takes" section.

Format: "[One surprising or interesting thing]. [What the paper actually does/shows]."

Paper Title: {title}
Abstract: {abstract}

Keep it under 50 words. No hype. Concrete.
"""


async def generate_quick_take(paper: ScoredPaper) -> QuickTake:
    """
    Generate a brief summary for a runner-up paper.
    """
    # TODO: Implement Quick Take generation
    #
    # 1. Format prompt with paper details
    # 2. Call LLM
    # 3. Parse response
    
    logger.info(f"Generating Quick Take for {paper.paper.arxiv_id}")
    raise NotImplementedError("Quick Take generation not yet implemented")


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
