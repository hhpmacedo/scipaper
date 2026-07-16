"""
Paper selection for weekly edition.
"""

import logging
from collections import Counter
from typing import List, Set
from dataclasses import dataclass

from .models import Paper, ScoredPaper, primary_area

logger = logging.getLogger(__name__)


@dataclass
class SelectionConfig:
    """Configuration for paper selection."""
    target_count: int = 8  # DEC-004: Curate 8-10 papers for verification buffer
    min_count: int = 3     # Minimum acceptable
    max_count: int = 10    # Maximum (for buffer)
    
    # Diversity constraints
    max_same_institution: int = 2
    max_same_topic: int = 2
    min_distinct_areas: int = 3   # every edition must span at least this many areas

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
    institution_counts: Counter = Counter()
    topic_counts: Counter = Counter()

    for paper in eligible:
        if len(selected) >= config.target_count:
            break

        # Check diversity constraints
        paper_institutions = _get_institutions(paper.paper)
        paper_topics = _get_topics(paper.paper)

        # Check if adding this paper would exceed institution limit
        inst_blocked = any(
            institution_counts[inst] >= config.max_same_institution
            for inst in paper_institutions
        ) if paper_institutions else False

        if inst_blocked:
            logger.debug(f"Skipping {paper.paper.arxiv_id}: institution diversity")
            continue

        # Check if adding this paper would exceed topic limit
        topic_blocked = any(
            topic_counts[topic] >= config.max_same_topic
            for topic in paper_topics
        ) if paper_topics else False

        if topic_blocked:
            logger.debug(f"Skipping {paper.paper.arxiv_id}: topic diversity")
            continue

        # Select this paper
        paper.selected_for_edition = True
        paper.selection_reason = f"Score: {paper.composite_score:.1f}"
        selected.append(paper)

        # Update tracking
        institution_counts.update(paper_institutions)
        topic_counts.update(paper_topics)
    
    logger.info(f"Selected {len(selected)} papers for edition")

    # Ensure the edition spans at least min_distinct_areas areas. area diversity
    # is a SOFT target: it never overrides the HARD max_same_institution cap. If a
    # missing area can only be covered by a paper that would breach the institution
    # cap, we skip it and ship with fewer areas.
    def _areas(papers):
        return Counter(primary_area(p.paper) for p in papers)

    def _inst_ok(cand, without=None):
        """True if adding cand keeps every institution <= max_same_institution,
        counting the current selection minus `without` (the paper being dropped)."""
        counts = Counter()
        for p in selected:
            if without is not None and p is without:
                continue
            counts.update(_get_institutions(p.paper))
        return all(
            counts[inst] < config.max_same_institution
            for inst in _get_institutions(cand.paper)
        )

    while len({primary_area(p.paper) for p in selected}) < config.min_distinct_areas:
        present = {primary_area(p.paper) for p in selected}
        area_counts = _areas(selected)
        droppable = sorted(
            (p for p in selected if area_counts[primary_area(p.paper)] > 1),
            key=lambda p: p.composite_score or 0,
        )
        drop = droppable[0] if droppable else None

        # Highest-scoring eligible missing-area paper whose institutions stay
        # within the hard cap (accounting for the drop, if any).
        candidate = next(
            (p for p in eligible
             if p not in selected
             and primary_area(p.paper) not in present
             and _inst_ok(p, without=drop)),
            None,
        )
        if candidate is None:
            logger.info(
                "Cannot reach min_distinct_areas without breaching institution cap; "
                "shipping with fewer areas"
            )
            break

        if drop is None:
            if len(selected) < config.max_count:
                candidate.selected_for_edition = True
                candidate.selection_reason = "Added for area diversity"
                selected.append(candidate)
                continue
            break
        drop.selected_for_edition = False
        selected.remove(drop)
        candidate.selected_for_edition = True
        candidate.selection_reason = "Swapped in for area diversity"
        selected.append(candidate)

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
    """A paper's coarse research area (single-element set) for diversity capping."""
    return {primary_area(paper)}


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
