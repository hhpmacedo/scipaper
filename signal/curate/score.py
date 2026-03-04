"""
Paper scoring on two axes: Relevance and Narrative Potential.
"""

import logging
from typing import List, Optional
from dataclasses import dataclass

from .models import Paper, AnchorDocument, ScoredPaper

logger = logging.getLogger(__name__)


@dataclass
class ScoringConfig:
    """Configuration for scoring."""
    # Weights for relevance scoring
    topic_match_weight: float = 0.4
    citation_velocity_weight: float = 0.2
    social_signal_weight: float = 0.2
    institution_weight: float = 0.2
    
    # LLM settings for narrative potential
    llm_model: str = "claude-3-5-sonnet-20241022"
    

async def score_relevance(
    paper: Paper,
    anchor: AnchorDocument,
    config: Optional[ScoringConfig] = None
) -> float:
    """
    Score paper relevance (1-10) based on:
    - Semantic similarity to hot_topics in anchor document
    - Keyword matches to boost_keywords
    - Institution signals
    - Citation velocity (citations / days since publication)
    - Social signal strength
    
    Returns float between 1 and 10.
    """
    config = config or ScoringConfig()
    
    # TODO: Implement relevance scoring
    # 
    # 1. Embed paper abstract
    # 2. Embed hot_topics from anchor
    # 3. Compute semantic similarity
    # 4. Check keyword matches
    # 5. Check institution matches
    # 6. Compute citation velocity
    # 7. Aggregate social signals
    # 8. Weighted combination
    
    logger.info(f"Scoring relevance for {paper.arxiv_id}")
    raise NotImplementedError("Relevance scoring not yet implemented")


NARRATIVE_POTENTIAL_PROMPT = """
You are evaluating a research paper's "narrative potential" for a newsletter that explains AI research to technically literate non-researchers.

Score this paper from 1-10 on narrative potential based on:

1. **Clear Problem/Solution** (0-2 points): Is there a clear problem being solved? Can you state it in one sentence?

2. **Surprising Result** (0-3 points): Is there something counterintuitive, unexpected, or "wow" worthy in the results?

3. **Concrete Examples** (0-2 points): Does the paper include demos, examples, or cases that would resonate with practitioners?

4. **Explainability** (0-2 points): Can the core idea be explained without heavy math? Would a software engineer get it?

5. **Practical Relevance** (0-1 point): Is there a clear "so what" for people who build things with AI?

Paper Title: {title}

Paper Abstract:
{abstract}

Respond with ONLY a JSON object:
{{
  "score": <1-10>,
  "problem_solution": <0-2>,
  "surprising_result": <0-3>,
  "concrete_examples": <0-2>,
  "explainability": <0-2>,
  "practical_relevance": <0-1>,
  "one_line_hook": "<the surprising thing, if any>",
  "reasoning": "<brief explanation>"
}}
"""


async def score_narrative_potential(
    paper: Paper,
    config: Optional[ScoringConfig] = None
) -> float:
    """
    Score paper narrative potential (1-10) using LLM assessment.
    
    Evaluates:
    - Is there a clear problem/solution structure?
    - Is there a surprising or counterintuitive result?
    - Are there concrete examples or demos?
    - Can this be explained without heavy math?
    - Is there a "so what" for practitioners?
    
    Returns float between 1 and 10.
    """
    config = config or ScoringConfig()
    
    # TODO: Implement narrative potential scoring
    #
    # 1. Format prompt with paper title and abstract
    # 2. Call LLM (Claude/GPT)
    # 3. Parse JSON response
    # 4. Return composite score
    
    logger.info(f"Scoring narrative potential for {paper.arxiv_id}")
    raise NotImplementedError("Narrative potential scoring not yet implemented")


def compute_composite_score(
    relevance: float,
    narrative_potential: float,
    relevance_weight: float = 0.5,
    narrative_weight: float = 0.5
) -> float:
    """
    Compute weighted composite score from relevance and narrative potential.
    
    Default: Equal weighting (50/50)
    """
    return (relevance * relevance_weight) + (narrative_potential * narrative_weight)


async def score_papers(
    papers: List[Paper],
    anchor: AnchorDocument,
    config: Optional[ScoringConfig] = None
) -> List[ScoredPaper]:
    """
    Score all papers on both axes.
    
    Returns list of ScoredPaper objects sorted by composite score.
    """
    config = config or ScoringConfig()
    scored = []
    
    for paper in papers:
        relevance = await score_relevance(paper, anchor, config)
        narrative = await score_narrative_potential(paper, config)
        composite = compute_composite_score(relevance, narrative)
        
        scored.append(ScoredPaper(
            paper=paper,
            relevance_score=relevance,
            narrative_potential_score=narrative,
            composite_score=composite
        ))
    
    # Sort by composite score, descending
    scored.sort(key=lambda x: x.composite_score, reverse=True)
    
    return scored
