"""
Paper scoring on two axes: Relevance and Narrative Potential.
"""

import json
import logging
import re
from typing import List, Optional
from dataclasses import dataclass


from .models import Paper, AnchorDocument, ScoredPaper
from ..retry import api_retry

logger = logging.getLogger(__name__)


@dataclass
class ScoringConfig:
    """Configuration for scoring."""
    # Weights for relevance scoring components
    topic_match_weight: float = 0.35
    keyword_match_weight: float = 0.20
    institution_weight: float = 0.15
    citation_velocity_weight: float = 0.15
    social_signal_weight: float = 0.15

    # LLM settings for narrative potential
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-4-20250514"
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None


def _text_similarity(text: str, topics: List[str]) -> float:
    """
    Compute keyword-based similarity between text and a list of topics.

    Uses token overlap as a lightweight alternative to embeddings.
    When sentence-transformers is available, this could be upgraded
    to use semantic embeddings.
    """
    if not topics:
        return 0.0

    text_lower = text.lower()
    text_tokens = set(re.findall(r'\b\w+\b', text_lower))

    max_score = 0.0
    for topic in topics:
        topic_lower = topic.lower()
        topic_tokens = set(re.findall(r'\b\w+\b', topic_lower))

        if not topic_tokens:
            continue

        # Check phrase match (higher weight)
        if topic_lower in text_lower:
            max_score = max(max_score, 1.0)
            continue

        # Token overlap
        overlap = len(text_tokens & topic_tokens) / len(topic_tokens)
        max_score = max(max_score, overlap)

    return max_score


def _keyword_score(paper: Paper, anchor: AnchorDocument) -> float:
    """Score based on keyword matches in title and abstract."""
    if not anchor.boost_keywords:
        return 0.0

    text = f"{paper.title} {paper.abstract}".lower()
    matches = sum(1 for kw in anchor.boost_keywords if kw.lower() in text)
    # Normalize: up to 3 matches = full score
    return min(matches / 3.0, 1.0)


def _institution_score(paper: Paper, anchor: AnchorDocument) -> float:
    """Score based on whether paper is from institutions of interest."""
    if not anchor.institutions_of_interest or not paper.authors:
        return 0.0

    for author in paper.authors:
        if author.affiliation:
            aff_lower = author.affiliation.lower()
            for inst in anchor.institutions_of_interest:
                if inst.lower() in aff_lower:
                    return 1.0

    # Also check if institution name appears in author names/paper text
    text = " ".join(a.name for a in paper.authors).lower()
    for inst in anchor.institutions_of_interest:
        if inst.lower() in text:
            return 0.5

    return 0.0


def _citation_velocity(paper: Paper) -> float:
    """
    Compute citation velocity: citations per day since publication.
    Normalized to 0-1 scale.
    """
    if not paper.published_date or paper.citation_count == 0:
        return 0.0

    from datetime import datetime, timezone
    days_since = (datetime.now(timezone.utc).replace(tzinfo=None) - paper.published_date.replace(tzinfo=None)).days
    if days_since <= 0:
        days_since = 1

    velocity = paper.citation_count / days_since
    # Normalize: 1+ citations/day is exceptional for new papers
    return min(velocity / 1.0, 1.0)


def _social_signal_score(paper: Paper) -> float:
    """Aggregate social signals into 0-1 score."""
    score = 0.0

    # HN: 10+ points is notable, 100+ is very notable
    if paper.hn_points > 0:
        score = max(score, min(paper.hn_points / 100.0, 1.0))

    # Twitter: 5+ mentions is notable
    if paper.twitter_mentions > 0:
        score = max(score, min(paper.twitter_mentions / 50.0, 1.0))

    # Reddit: 10+ score is notable
    if paper.reddit_score > 0:
        score = max(score, min(paper.reddit_score / 100.0, 1.0))

    return score


def _declining_topic_penalty(paper: Paper, anchor: AnchorDocument) -> float:
    """Return a penalty (0-1) if paper matches declining topics."""
    if not anchor.declining_topics:
        return 0.0

    text = f"{paper.title} {paper.abstract}".lower()
    for topic in anchor.declining_topics:
        if topic.lower() in text:
            return 0.3  # 30% penalty

    return 0.0


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

    # Compute individual components (each 0-1)
    topic_sim = _text_similarity(
        f"{paper.title} {paper.abstract}", anchor.hot_topics
    )
    keyword = _keyword_score(paper, anchor)
    institution = _institution_score(paper, anchor)
    citation_vel = _citation_velocity(paper)
    social = _social_signal_score(paper)

    # Weighted combination (0-1 scale)
    raw_score = (
        topic_sim * config.topic_match_weight
        + keyword * config.keyword_match_weight
        + institution * config.institution_weight
        + citation_vel * config.citation_velocity_weight
        + social * config.social_signal_weight
    )

    # Apply declining topic penalty
    penalty = _declining_topic_penalty(paper, anchor)
    raw_score = raw_score * (1.0 - penalty)

    # Scale to 1-10
    score = max(1.0, min(10.0, raw_score * 9.0 + 1.0))

    logger.debug(
        f"Relevance for {paper.arxiv_id}: {score:.1f} "
        f"(topic={topic_sim:.2f}, kw={keyword:.2f}, inst={institution:.2f}, "
        f"cite={citation_vel:.2f}, social={social:.2f})"
    )

    return round(score, 2)


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

    Returns float between 1 and 10.
    """
    config = config or ScoringConfig()

    prompt = NARRATIVE_POTENTIAL_PROMPT.format(
        title=paper.title,
        abstract=paper.abstract,
    )

    try:
        if config.llm_provider == "anthropic":
            score = await _score_with_anthropic(prompt, config)
        elif config.llm_provider == "openai":
            score = await _score_with_openai(prompt, config)
        else:
            raise ValueError(f"Unknown LLM provider: {config.llm_provider}")

        score = max(1.0, min(10.0, float(score)))
        logger.debug(f"Narrative potential for {paper.arxiv_id}: {score:.1f}")
        return round(score, 2)

    except Exception as e:
        logger.warning(
            f"LLM scoring failed for {paper.arxiv_id}, using heuristic: {e}"
        )
        return _heuristic_narrative_score(paper)


@api_retry
async def _score_with_anthropic(prompt: str, config: ScoringConfig) -> float:
    """Score using Anthropic API."""
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)
    response = await client.messages.create(
        model=config.llm_model,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )

    return _parse_score_response(response.content[0].text)


@api_retry
async def _score_with_openai(prompt: str, config: ScoringConfig) -> float:
    """Score using OpenAI API."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=config.openai_api_key)
    response = await client.chat.completions.create(
        model=config.llm_model,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )

    return _parse_score_response(response.choices[0].message.content)


def _parse_score_response(text: str) -> float:
    """Parse score from LLM JSON response."""
    # Try to extract JSON from the response
    text = text.strip()

    # Handle markdown code blocks
    if "```" in text:
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            text = match.group(1)

    try:
        data = json.loads(text)
        return float(data["score"])
    except (json.JSONDecodeError, KeyError, ValueError):
        # Try to find a number in the response
        match = re.search(r'"score"\s*:\s*(\d+(?:\.\d+)?)', text)
        if match:
            return float(match.group(1))
        raise ValueError(f"Could not parse score from response: {text[:200]}")


def _heuristic_narrative_score(paper: Paper) -> float:
    """
    Fallback heuristic scoring when LLM is unavailable.
    Based on abstract characteristics.
    """
    score = 5.0  # Base score
    abstract = paper.abstract.lower()

    # Positive signals
    if any(w in abstract for w in ["surprising", "unexpected", "contrary"]):
        score += 1.0
    if any(w in abstract for w in ["demonstrate", "demo", "example", "show that"]):
        score += 0.5
    if any(w in abstract for w in ["practical", "application", "deploy", "production"]):
        score += 0.5
    if any(w in abstract for w in ["outperform", "state-of-the-art", "sota", "benchmark"]):
        score += 0.5
    if any(w in abstract for w in ["open-source", "open source", "code available"]):
        score += 0.5

    # Negative signals
    if any(w in abstract for w in ["theoretical", "proof", "theorem"]):
        score -= 0.5
    if len(abstract) < 200:
        score -= 0.5

    return max(1.0, min(10.0, score))


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
    return round(
        (relevance * relevance_weight) + (narrative_potential * narrative_weight),
        2,
    )


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
        try:
            relevance = await score_relevance(paper, anchor, config)
            narrative = await score_narrative_potential(paper, config)
            composite = compute_composite_score(relevance, narrative)

            scored.append(ScoredPaper(
                paper=paper,
                relevance_score=relevance,
                narrative_potential_score=narrative,
                composite_score=composite,
            ))
        except Exception as e:
            logger.warning(f"Failed to score {paper.arxiv_id}: {e}")
            continue

    # Sort by composite score, descending
    scored.sort(key=lambda x: x.composite_score, reverse=True)

    logger.info(f"Scored {len(scored)}/{len(papers)} papers")
    return scored
