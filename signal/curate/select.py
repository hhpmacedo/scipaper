"""
Paper selection for weekly edition.
"""

import logging
from typing import List, Set
from dataclasses import dataclass

from .models import Paper, ScoredPaper

logger = logging.getLogger(__name__)


@dataclass
class SelectionConfig:
    """Configuration for paper selection."""
    target_count: int = 5  # Number of papers to select
    min_count: int = 3     # Minimum acceptable
    max_count: int = 8     # Maximum (for buffer)
    
    # Diversity constraints
    max_same_institution: int = 2
    max_same_topic: int = 2
    
    # Score thresholds
    min_relevance: float = 4.0
    min_narrative_potential: float = 5.0


def select_edition_papers(
    scored_papers: List[ScoredPaper],
    config: SelectionConfig = None
) -> List[ScoredPaper]:
    """
    Select papers for this week's edition.
    
    Selection criteria:
    1. Composite score (primary)
    2. Diversity (different topics, institutions)
    3. Minimum thresholds (relevance >= 4, narrative >= 5)
    
    Returns list of selected ScoredPaper objects.
    """
    config = config or SelectionConfig()
    
    # Filter by minimum thresholds
    eligible = [
        p for p in scored_papers
        if p.relevance_score >= config.min_relevance
        and p.narrative_potential_score >= config.min_narrative_potential
    ]
    
    logger.info(f"{len(eligible)} papers pass minimum thresholds")
    
    if len(eligible) < config.min_count:
        logger.warning(
            f"Only {len(eligible)} eligible papers, below minimum {config.min_count}"
        )
    
    # Greedy selection with diversity constraints
    selected: List[ScoredPaper] = []
    institutions_used: Set[str] = set()
    topics_used: Set[str] = set()
    
    for paper in eligible:
        if len(selected) >= config.target_count:
            break
            
        # Check diversity constraints
        paper_institutions = _get_institutions(paper.paper)
        paper_topics = _get_topics(paper.paper)
        
        # Count overlap
        inst_overlap = len(institutions_used & paper_institutions)
        topic_overlap = len(topics_used & paper_topics)
        
        if inst_overlap >= config.max_same_institution:
            logger.debug(f"Skipping {paper.paper.arxiv_id}: institution diversity")
            continue
            
        if topic_overlap >= config.max_same_topic:
            logger.debug(f"Skipping {paper.paper.arxiv_id}: topic diversity")
            continue
        
        # Select this paper
        paper.selected_for_edition = True
        paper.selection_reason = f"Score: {paper.composite_score:.1f}"
        selected.append(paper)
        
        # Update tracking
        institutions_used.update(paper_institutions)
        topics_used.update(paper_topics)
    
    logger.info(f"Selected {len(selected)} papers for edition")
    
    # If we don't have enough, relax constraints and try again
    if len(selected) < config.min_count:
        logger.warning("Relaxing diversity constraints to meet minimum")
        remaining = [p for p in eligible if p not in selected]
        for paper in remaining[:config.min_count - len(selected)]:
            paper.selected_for_edition = True
            paper.selection_reason = "Selected to meet minimum (relaxed constraints)"
            selected.append(paper)
    
    return selected


def _get_institutions(paper: Paper) -> Set[str]:
    """Extract institution names from paper authors."""
    institutions = set()
    for author in paper.authors:
        if author.affiliation:
            # Normalize institution names
            aff = author.affiliation.lower()
            # Common institution keywords
            for inst in ["openai", "anthropic", "deepmind", "google", "meta", 
                        "microsoft", "stanford", "mit", "berkeley", "cmu"]:
                if inst in aff:
                    institutions.add(inst)
    return institutions


def _get_topics(paper: Paper) -> Set[str]:
    """Extract topic categories from paper."""
    # Use ArXiv categories as proxy for topics
    return set(paper.categories)


def get_runners_up(
    scored_papers: List[ScoredPaper],
    selected: List[ScoredPaper],
    count: int = 5
) -> List[ScoredPaper]:
    """
    Get runners-up papers for Quick Takes section.
    
    These are papers that didn't make the main selection but are still
    notable enough to mention briefly.
    """
    selected_ids = {p.paper.arxiv_id for p in selected}
    
    runners_up = [
        p for p in scored_papers
        if p.paper.arxiv_id not in selected_ids
        and p.relevance_score >= 4.0  # Still relevant
    ]
    
    return runners_up[:count]
