"""
Tests for the paper selection module.
"""

from datetime import datetime, timezone


from scipaper.curate.models import Author, Paper, ScoredPaper
from scipaper.curate.select import (
    SelectionConfig,
    _get_institutions,
    _get_topics,
    get_runners_up,
    select_edition_papers,
)


def make_scored_paper(
    arxiv_id="2403.12345",
    relevance=7.0,
    narrative=7.0,
    categories=None,
    affiliation=None,
    **kwargs,
):
    categories = categories or ["cs.AI"]
    paper = Paper(
        arxiv_id=arxiv_id,
        title=kwargs.get("title", f"Paper {arxiv_id}"),
        abstract=kwargs.get("abstract", "Test abstract"),
        authors=[Author(name="Author", affiliation=affiliation)],
        categories=categories,
        published_date=datetime.now(timezone.utc),
    )
    return ScoredPaper(
        paper=paper,
        relevance_score=relevance,
        narrative_potential_score=narrative,
        composite_score=(relevance + narrative) / 2,
    )


class TestSelectionConfigDefaults:
    def test_default_target_count_is_8(self):
        """DEC-004: Default selection targets 8 papers for verification buffer."""
        config = SelectionConfig()
        assert config.target_count == 8

    def test_default_max_count_is_10(self):
        """DEC-004: Max count is 10 for buffer."""
        config = SelectionConfig()
        assert config.max_count == 10


class TestSelectEditionPapers:
    def test_selects_target_count(self):
        # Use varied categories to avoid hitting topic diversity limits
        cats = [["cs.AI"], ["cs.LG"], ["cs.CL"], ["stat.ML"], ["cs.AI", "cs.LG"]]
        papers = [
            make_scored_paper(arxiv_id=str(i), categories=cats[i % len(cats)])
            for i in range(10)
        ]
        config = SelectionConfig(target_count=5)
        selected = select_edition_papers(papers, config)
        assert len(selected) == 5

    def test_filters_by_minimum_scores(self):
        papers = [
            make_scored_paper(arxiv_id="1", relevance=8.0, narrative=8.0),
            make_scored_paper(arxiv_id="2", relevance=2.0, narrative=3.0),
            make_scored_paper(arxiv_id="3", relevance=7.0, narrative=7.0),
        ]
        config = SelectionConfig(
            target_count=5,
            min_relevance=4.0,
            min_narrative_potential=5.0,
        )
        selected = select_edition_papers(papers, config)
        selected_ids = {p.paper.arxiv_id for p in selected}
        assert "2" not in selected_ids

    def test_enforces_institution_diversity(self):
        # Provide enough diverse papers so relaxation isn't needed
        papers = [
            make_scored_paper(arxiv_id="1", relevance=9.0, narrative=9.0, affiliation="OpenAI Research", categories=["cs.AI"]),
            make_scored_paper(arxiv_id="2", relevance=8.5, narrative=8.5, affiliation="OpenAI Research", categories=["cs.LG"]),
            make_scored_paper(arxiv_id="3", relevance=8.0, narrative=8.0, affiliation="OpenAI Research", categories=["cs.CL"]),
            make_scored_paper(arxiv_id="4", relevance=7.5, narrative=7.5, affiliation="DeepMind", categories=["stat.ML"]),
            make_scored_paper(arxiv_id="5", relevance=7.0, narrative=7.0, affiliation="Anthropic Research", categories=["cs.AI", "cs.LG"]),
        ]
        config = SelectionConfig(target_count=4, max_same_institution=2, min_count=2)
        selected = select_edition_papers(papers, config)

        openai_count = sum(
            1 for p in selected
            if any("openai" in (a.affiliation or "").lower() for a in p.paper.authors)
        )
        assert openai_count <= 2

    def test_enforces_topic_diversity(self):
        papers = [
            make_scored_paper(arxiv_id="1", relevance=9.0, narrative=9.0, categories=["cs.AI"]),
            make_scored_paper(arxiv_id="2", relevance=8.5, narrative=8.5, categories=["cs.AI"]),
            make_scored_paper(arxiv_id="3", relevance=8.0, narrative=8.0, categories=["cs.AI"]),
            make_scored_paper(arxiv_id="4", relevance=7.0, narrative=7.0, categories=["cs.CL"]),
        ]
        config = SelectionConfig(target_count=4, max_same_topic=2)
        selected = select_edition_papers(papers, config)

        ai_count = sum(1 for p in selected if "cs.AI" in p.paper.categories)
        assert ai_count <= 2

    def test_relaxes_constraints_for_minimum(self):
        papers = [
            make_scored_paper(arxiv_id="1", relevance=9.0, narrative=9.0, categories=["cs.AI"]),
            make_scored_paper(arxiv_id="2", relevance=8.0, narrative=8.0, categories=["cs.AI"]),
            make_scored_paper(arxiv_id="3", relevance=7.0, narrative=7.0, categories=["cs.AI"]),
        ]
        config = SelectionConfig(target_count=3, min_count=3, max_same_topic=1)
        selected = select_edition_papers(papers, config)
        assert len(selected) >= config.min_count

    def test_marks_selected(self):
        papers = [make_scored_paper(arxiv_id="1")]
        selected = select_edition_papers(papers, SelectionConfig(target_count=1))
        assert selected[0].selected_for_edition is True
        assert selected[0].selection_reason is not None

    def test_empty_input(self):
        selected = select_edition_papers([])
        assert selected == []


class TestGetInstitutions:
    def test_known_institutions(self):
        paper = Paper(
            arxiv_id="1",
            title="Test",
            abstract="Test",
            authors=[
                Author(name="A", affiliation="OpenAI Research"),
                Author(name="B", affiliation="Stanford CS"),
            ],
        )
        insts = _get_institutions(paper)
        assert "openai" in insts
        assert "stanford" in insts

    def test_no_affiliation(self):
        paper = Paper(
            arxiv_id="1",
            title="Test",
            abstract="Test",
            authors=[Author(name="A")],
        )
        assert _get_institutions(paper) == set()


class TestGetTopics:
    def test_returns_categories(self):
        paper = Paper(
            arxiv_id="1",
            title="Test",
            abstract="Test",
            categories=["cs.AI", "cs.LG"],
        )
        assert _get_topics(paper) == {"cs.AI", "cs.LG"}


class TestGetRunnersUp:
    def test_excludes_selected(self):
        all_papers = [
            make_scored_paper(arxiv_id="1", relevance=9.0, narrative=9.0),
            make_scored_paper(arxiv_id="2", relevance=7.0, narrative=7.0),
            make_scored_paper(arxiv_id="3", relevance=6.0, narrative=6.0),
        ]
        selected = [all_papers[0]]
        runners = get_runners_up(all_papers, selected, count=5)
        runner_ids = {p.paper.arxiv_id for p in runners}
        assert "1" not in runner_ids
        assert "2" in runner_ids

    def test_respects_count(self):
        all_papers = [make_scored_paper(arxiv_id=str(i)) for i in range(10)]
        runners = get_runners_up(all_papers, [], count=3)
        assert len(runners) == 3
