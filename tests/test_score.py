"""
Tests for the paper scoring module.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch


from .conftest import run_async

from scipaper.curate.models import AnchorDocument, Author, Paper, ScoredPaper
from scipaper.curate.score import (
    ScoringConfig,
    _citation_velocity,
    _heuristic_narrative_score,
    _institution_score,
    _keyword_score,
    _parse_score_response,
    _social_signal_score,
    _text_similarity,
    compute_composite_score,
    score_narrative_potential,
    score_papers,
    score_papers_two_pass,
    score_relevance,
)


def make_paper(**kwargs):
    defaults = dict(
        arxiv_id="2403.12345",
        title="Reasoning Models and Test-Time Compute Scaling",
        abstract="We present a method for scaling test-time compute in reasoning models, achieving state-of-the-art results on mathematical benchmarks.",
        authors=[
            Author(name="Alice Smith", affiliation="Anthropic"),
            Author(name="Bob Jones", affiliation="Stanford University"),
        ],
        categories=["cs.AI", "cs.LG"],
        published_date=datetime.now(timezone.utc) - timedelta(days=3),
        citation_count=5,
        hn_points=50,
    )
    defaults.update(kwargs)
    return Paper(**defaults)


def make_anchor(**kwargs):
    defaults = dict(
        week="2026-W10",
        updated_by="test",
        updated_at=datetime.now(timezone.utc),
        hot_topics=[
            "reasoning models and test-time compute",
            "multimodal understanding beyond CLIP",
            "efficient fine-tuning methods",
        ],
        declining_topics=["basic prompt engineering", "GPT wrappers"],
        boost_keywords=["o1", "o3", "claude", "reasoning", "agent"],
        institutions_of_interest=["Anthropic", "OpenAI", "DeepMind", "Stanford"],
    )
    defaults.update(kwargs)
    return AnchorDocument(**defaults)


class TestTextSimilarity:
    def test_exact_match(self):
        score = _text_similarity(
            "reasoning models and test-time compute",
            ["reasoning models and test-time compute"],
        )
        assert score == 1.0

    def test_partial_match(self):
        score = _text_similarity(
            "We study reasoning in large language models",
            ["reasoning models and test-time compute"],
        )
        assert 0.0 < score < 1.0

    def test_no_match(self):
        score = _text_similarity(
            "quantum computing applications",
            ["reasoning models and test-time compute"],
        )
        assert score < 0.5

    def test_empty_topics(self):
        assert _text_similarity("some text", []) == 0.0


class TestKeywordScore:
    def test_multiple_matches(self):
        paper = make_paper(title="Claude o1 reasoning agent benchmark")
        anchor = make_anchor()
        score = _keyword_score(paper, anchor)
        assert score > 0.5

    def test_no_matches(self):
        paper = make_paper(title="Quantum Computing Paper", abstract="About qubits")
        anchor = make_anchor()
        score = _keyword_score(paper, anchor)
        assert score == 0.0

    def test_empty_keywords(self):
        paper = make_paper()
        anchor = make_anchor(boost_keywords=[])
        assert _keyword_score(paper, anchor) == 0.0


class TestInstitutionScore:
    def test_matching_affiliation(self):
        paper = make_paper(
            authors=[Author(name="Test", affiliation="Anthropic Research")]
        )
        anchor = make_anchor()
        assert _institution_score(paper, anchor) == 1.0

    def test_no_match(self):
        paper = make_paper(
            authors=[Author(name="Test", affiliation="Unknown Lab")]
        )
        anchor = make_anchor()
        assert _institution_score(paper, anchor) == 0.0

    def test_no_affiliation(self):
        paper = make_paper(authors=[Author(name="Test")])
        anchor = make_anchor()
        assert _institution_score(paper, anchor) == 0.0


class TestCitationVelocity:
    def test_high_velocity(self):
        paper = make_paper(
            published_date=datetime.now(timezone.utc) - timedelta(days=2),
            citation_count=5,
        )
        score = _citation_velocity(paper)
        assert score > 0.5

    def test_zero_citations(self):
        paper = make_paper(citation_count=0)
        assert _citation_velocity(paper) == 0.0

    def test_no_date(self):
        paper = make_paper(published_date=None)
        assert _citation_velocity(paper) == 0.0


class TestSocialSignalScore:
    def test_hn_points(self):
        paper = make_paper(hn_points=50, twitter_mentions=0, reddit_score=0)
        assert _social_signal_score(paper) == 0.5

    def test_no_signals(self):
        paper = make_paper(hn_points=0, twitter_mentions=0, reddit_score=0)
        assert _social_signal_score(paper) == 0.0


class TestCommunitySignalScore:
    def test_hf_upvotes_raise_social_score(self):
        paper = make_paper(hn_points=0, twitter_mentions=0, reddit_score=0, hf_upvotes=100)
        assert _social_signal_score(paper) == 1.0

    def test_github_stars_raise_social_score(self):
        paper = make_paper(hn_points=0, twitter_mentions=0, reddit_score=0, github_stars=250)
        assert _social_signal_score(paper) == 0.5

    def test_no_community_signals(self):
        paper = make_paper(hn_points=0, twitter_mentions=0, reddit_score=0, hf_upvotes=0, github_stars=0)
        assert _social_signal_score(paper) == 0.0

    def test_hf_upvotes_raise_relevance_score(self):
        anchor = make_anchor()
        base = dict(
            arxiv_id="a", title="agents paper", abstract="about agents",
            hn_points=0, twitter_mentions=0, reddit_score=0,
        )
        plain = Paper(**base)
        with_upvotes = Paper(**base, hf_upvotes=200)
        s_plain = run_async(score_relevance(plain, anchor))
        s_with_upvotes = run_async(score_relevance(with_upvotes, anchor))
        assert s_with_upvotes > s_plain


class TestScoreRelevance:
    def test_relevant_paper_scores_high(self):
        paper = make_paper()
        anchor = make_anchor()
        score = run_async(score_relevance(paper, anchor))
        assert 4.0 <= score <= 10.0

    def test_irrelevant_paper_scores_low(self):
        paper = make_paper(
            title="Fluid Dynamics Simulation",
            abstract="We simulate turbulent flows using finite element methods.",
            authors=[Author(name="Test", affiliation="Physics Dept")],
            categories=["physics.flu-dyn"],
            citation_count=0,
            hn_points=0,
        )
        anchor = make_anchor()
        score = run_async(score_relevance(paper, anchor))
        assert 1.0 <= score <= 4.0

    def test_score_within_bounds(self):
        paper = make_paper()
        anchor = make_anchor()
        score = run_async(score_relevance(paper, anchor))
        assert 1.0 <= score <= 10.0


def test_quality_signal_raises_relevance():
    from scipaper.curate.score import score_relevance, ScoringConfig
    from scipaper.curate.models import Paper, AnchorDocument
    from .conftest import run_async
    from datetime import datetime, timezone

    anchor = AnchorDocument(week="2026-W29", updated_by="t", updated_at=datetime.now(timezone.utc),
                            hot_topics=["agents"])
    base = dict(arxiv_id="a", title="agents paper", abstract="about agents")
    plain = Paper(**base)
    strong = Paper(**base, influential_citation_count=20, max_author_h_index=60)
    s_plain = run_async(score_relevance(plain, anchor, ScoringConfig()))
    s_strong = run_async(score_relevance(strong, anchor, ScoringConfig()))
    assert s_strong > s_plain


def test_scoring_weights_sum_to_one():
    from scipaper.curate.score import ScoringConfig
    c = ScoringConfig()
    total = (c.topic_match_weight + c.keyword_match_weight + c.institution_weight
             + c.citation_velocity_weight + c.social_signal_weight + c.quality_signal_weight
             + c.prestige_weight)
    assert abs(total - 1.0) < 1e-9


def test_prestige_lab_raises_relevance():
    from scipaper.curate.score import score_relevance, ScoringConfig
    from scipaper.curate.models import Paper, Author, AnchorDocument
    from .conftest import run_async
    from datetime import datetime, timezone
    anchor = AnchorDocument(week="2026-W29", updated_by="t", updated_at=datetime.now(timezone.utc), hot_topics=["agents"])
    cfg = ScoringConfig(prestige={"labs": ["deepmind"], "authors": []})
    plain = Paper(arxiv_id="a", title="agents", abstract="agents", authors=[Author(name="X", affiliation="Startup")])
    prestige = Paper(arxiv_id="b", title="agents", abstract="agents", authors=[Author(name="Y", affiliation="Google DeepMind")])
    assert run_async(score_relevance(prestige, anchor, cfg)) > run_async(score_relevance(plain, anchor, cfg))


class TestParseScoreResponse:
    def test_valid_json(self):
        response = '{"score": 7, "reasoning": "good paper"}'
        assert _parse_score_response(response) == 7.0

    def test_json_in_code_block(self):
        response = '```json\n{"score": 8}\n```'
        assert _parse_score_response(response) == 8.0

    def test_float_score(self):
        response = '{"score": 6.5, "reasoning": "decent"}'
        assert _parse_score_response(response) == 6.5


class TestHeuristicNarrativeScore:
    def test_practical_paper(self):
        paper = make_paper(
            abstract="We demonstrate a practical application that outperforms state-of-the-art benchmarks. Code available as open-source."
        )
        score = _heuristic_narrative_score(paper)
        assert score > 5.0

    def test_theoretical_paper(self):
        paper = make_paper(
            abstract="We prove a theorem about convergence bounds."
        )
        score = _heuristic_narrative_score(paper)
        assert score <= 5.0


class TestCompositeScore:
    def test_equal_weights(self):
        assert compute_composite_score(8.0, 6.0) == 7.0

    def test_custom_weights(self):
        assert compute_composite_score(10.0, 0.0, relevance_weight=1.0, narrative_weight=0.0) == 10.0


class TestScoreNarrativePotential:
    def test_falls_back_to_heuristic(self):
        paper = make_paper()
        config = ScoringConfig(
            llm_provider="anthropic",
            anthropic_api_key="invalid-key",
        )

        with patch("scipaper.curate.score._score_with_anthropic", side_effect=Exception("API error")):
            score = run_async(score_narrative_potential(paper, config))

        assert 1.0 <= score <= 10.0


class TestScorePapers:
    def test_scores_and_sorts(self):
        papers = [
            make_paper(arxiv_id="1", title="Irrelevant Paper", abstract="Fluid dynamics"),
            make_paper(arxiv_id="2", title="Reasoning model scaling", abstract="Test-time compute for reasoning"),
        ]
        anchor = make_anchor()

        async def run_test():
            with patch("scipaper.curate.score._score_with_anthropic", side_effect=Exception("no api")):
                return await score_papers(papers, anchor)

        scored = run_async(run_test())

        assert len(scored) == 2
        assert scored[0].composite_score >= scored[1].composite_score
        assert all(isinstance(sp, ScoredPaper) for sp in scored)


class TestTwoPassScoring:
    def test_only_top_n_get_narrative_scored(self):
        """Only top N by relevance should have LLM narrative scoring called."""
        papers = [
            make_paper(arxiv_id=str(i), title=f"Paper {i}", abstract=f"Abstract {i}")
            for i in range(10)
        ]
        anchor = make_anchor()

        llm_call_count = 0

        async def mock_score_anthropic(prompt, config):
            nonlocal llm_call_count
            llm_call_count += 1
            return 5.0

        async def run_test():
            with patch("scipaper.curate.score._score_with_anthropic", side_effect=mock_score_anthropic):
                config = ScoringConfig(relevance_cutoff_count=3)
                return await score_papers_two_pass(papers, anchor, config)

        scored = run_async(run_test())
        assert llm_call_count == 3  # Only top 3 got LLM scoring
        assert len(scored) == 10  # All papers returned

    def test_two_pass_sorts_by_composite(self):
        papers = [
            make_paper(arxiv_id="1", title="Irrelevant Paper", abstract="Fluid dynamics"),
            make_paper(arxiv_id="2", title="Reasoning model scaling", abstract="Test-time compute for reasoning"),
        ]
        anchor = make_anchor()

        async def run_test():
            with patch("scipaper.curate.score._score_with_anthropic", side_effect=Exception("no api")):
                return await score_papers_two_pass(papers, anchor)

        scored = run_async(run_test())
        assert scored[0].composite_score >= scored[1].composite_score
