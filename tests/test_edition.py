"""
Tests for the edition assembly module.
"""

from datetime import datetime
from unittest.mock import AsyncMock, patch


from .conftest import run_async

from scipaper.generate.edition import (
    AssemblyConfig,
    Edition,
    QuickTake,
    _fallback_quick_take,
    assemble_edition,
    generate_edition_subject,
)
from scipaper.generate.writer import Piece
from scipaper.curate.models import Author, Paper, ScoredPaper


def make_piece(paper_id="2403.12345", title="Test Piece", hook="A surprising finding."):
    return Piece(
        paper_id=paper_id,
        title=title,
        hook=hook,
        content="Test content [§1]. More content [§2].",
        word_count=6,
        citations=[{"claim": "test", "citation": "§1"}],
        generated_at="2025-01-01T00:00:00",
        model_used="test",
    )


def make_scored_paper(arxiv_id="2403.12345", title="Test Paper", abstract="Test abstract."):
    paper = Paper(
        arxiv_id=arxiv_id,
        title=title,
        abstract=abstract,
        authors=[Author(name="Alice")],
        categories=["cs.AI"],
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
    )
    return ScoredPaper(
        paper=paper,
        relevance_score=8.0,
        narrative_potential_score=7.0,
        composite_score=7.5,
    )


class TestEdition:
    def test_post_init_sets_created_at(self):
        ed = Edition(week="2026-W10", issue_number=1)
        assert ed.created_at is not None

    def test_preserves_provided_created_at(self):
        dt = datetime(2025, 1, 1)
        ed = Edition(week="2026-W10", issue_number=1, created_at=dt)
        assert ed.created_at == dt


class TestQuickTake:
    def test_dataclass(self):
        qt = QuickTake(
            paper_id="test",
            title="Test Paper",
            one_liner="A brief summary.",
            paper_url="https://arxiv.org/abs/test",
        )
        assert qt.paper_id == "test"


class TestFallbackQuickTake:
    def test_uses_first_sentence(self):
        sp = make_scored_paper(abstract="First sentence here. Second sentence.")
        qt = _fallback_quick_take(sp)
        assert qt.one_liner == "First sentence here."

    def test_truncates_long_abstract(self):
        long_abstract = " ".join(["word"] * 100) + "."
        sp = make_scored_paper(abstract=long_abstract)
        qt = _fallback_quick_take(sp)
        assert len(qt.one_liner.split()) <= 51  # 50 + "..."

    def test_uses_title_for_empty_abstract(self):
        sp = make_scored_paper(abstract="")
        qt = _fallback_quick_take(sp)
        assert qt.one_liner == sp.paper.title


class TestAssembleEdition:
    def test_basic_assembly(self):
        pieces = [make_piece(paper_id=str(i)) for i in range(3)]
        runners = [make_scored_paper(arxiv_id=str(i + 10)) for i in range(2)]

        # Mock generate_quick_take to avoid LLM calls
        with patch("scipaper.generate.edition.generate_quick_take", new_callable=AsyncMock) as mock_qt:
            mock_qt.side_effect = [
                QuickTake(paper_id=str(i + 10), title=f"Paper {i}", one_liner="Summary.", paper_url="https://arxiv.org")
                for i in range(2)
            ]
            edition = run_async(assemble_edition(pieces, runners, "2026-W10", 1))

        assert edition.week == "2026-W10"
        assert edition.issue_number == 1
        assert len(edition.pieces) == 3
        assert len(edition.quick_takes) == 2
        assert edition.total_words > 0

    def test_respects_max_pieces(self):
        pieces = [make_piece(paper_id=str(i)) for i in range(10)]
        config = AssemblyConfig(max_pieces=3, max_quick_takes=0)

        edition = run_async(assemble_edition(pieces, [], "2026-W10", 1, config))
        assert len(edition.pieces) == 3

    def test_quick_take_fallback_on_error(self):
        pieces = [make_piece()]
        runners = [make_scored_paper(arxiv_id="r1")]

        with patch("scipaper.generate.edition.generate_quick_take", new_callable=AsyncMock) as mock_qt:
            mock_qt.side_effect = Exception("API error")
            edition = run_async(assemble_edition(pieces, runners, "2026-W10", 1))

        # Should still have a quick take from fallback
        assert len(edition.quick_takes) == 1


class TestGenerateEditionSubject:
    def test_with_pieces(self):
        ed = Edition(
            week="2026-W10",
            issue_number=42,
            pieces=[make_piece(hook="A surprising finding about LLMs")],
        )
        subject = generate_edition_subject(ed)
        assert "Signal #42" in subject
        assert "surprising" in subject

    def test_truncates_long_hook(self):
        long_hook = "A" * 80
        ed = Edition(
            week="2026-W10",
            issue_number=1,
            pieces=[make_piece(hook=long_hook)],
        )
        subject = generate_edition_subject(ed)
        assert len(subject) < 80

    def test_fallback_without_pieces(self):
        ed = Edition(week="2026-W10", issue_number=1)
        subject = generate_edition_subject(ed)
        assert "Signal #1" in subject
        assert "This Week" in subject
