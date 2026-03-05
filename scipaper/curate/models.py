"""
Data models for the curation pipeline.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List
from enum import Enum


class PaperCategory(str, Enum):
    """ArXiv categories we track."""
    CS_AI = "cs.AI"
    CS_LG = "cs.LG"  
    CS_CL = "cs.CL"
    STAT_ML = "stat.ML"


@dataclass
class Author:
    """Paper author."""
    name: str
    affiliation: Optional[str] = None


@dataclass
class Paper:
    """
    A research paper with metadata and scores.
    """
    # Core identifiers
    arxiv_id: str
    title: str
    abstract: str
    
    # Metadata
    authors: List[Author] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    published_date: Optional[datetime] = None
    pdf_url: Optional[str] = None
    
    # Semantic Scholar enrichment
    semantic_scholar_id: Optional[str] = None
    citation_count: int = 0
    reference_count: int = 0
    
    # Social signals
    twitter_mentions: int = 0
    hn_points: int = 0
    reddit_score: int = 0
    
    # Processing state
    ingested_at: Optional[datetime] = None
    pdf_parsed: bool = False
    full_text: Optional[str] = None
    
    # Scores (computed)
    relevance_score: Optional[float] = None
    narrative_potential_score: Optional[float] = None
    composite_score: Optional[float] = None
    
    def __post_init__(self):
        if self.ingested_at is None:
            self.ingested_at = datetime.now(timezone.utc)


@dataclass
class AnchorDocument:
    """
    Weekly relevance anchor document.
    The only human input in the entire system.
    """
    week: str  # ISO week format: 2025-W10
    updated_by: str
    updated_at: datetime
    
    hot_topics: List[str] = field(default_factory=list)
    declining_topics: List[str] = field(default_factory=list)
    boost_keywords: List[str] = field(default_factory=list)
    institutions_of_interest: List[str] = field(default_factory=list)


@dataclass
class ScoredPaper:
    """
    A paper with its scores and selection status.
    """
    paper: Paper
    relevance_score: float  # 1-10
    narrative_potential_score: float  # 1-10
    composite_score: float
    
    selected_for_edition: bool = False
    selection_reason: Optional[str] = None
