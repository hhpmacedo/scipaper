"""
Curation Pipeline

Discovers, scores, and selects papers for each week's edition.
"""

from .ingest import ingest_papers
from .score import score_relevance, score_narrative_potential
from .select import select_edition_papers

__all__ = [
    "ingest_papers",
    "score_relevance", 
    "score_narrative_potential",
    "select_edition_papers",
]
