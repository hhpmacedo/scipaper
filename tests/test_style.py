"""
Tests for the style compliance checker.
"""

import pytest

from .conftest import run_async

from scipaper.verify.style import (
    StyleConfig,
    check_banned_words,
    check_citations,
    check_structure,
    check_style_compliance,
    check_word_count,
)
from scipaper.generate.writer import Piece


def make_piece(content=None, **kwargs):
    if content is None:
        content = (
            "Hook sentence.\n\n"
            "## The Problem\nThis is the problem description [§1].\n\n"
            "## What They Did\nThey did this approach [§2.1]. "
            "With concrete details [Table 1].\n\n"
            "## The Results\nResults showed improvement [§3]. "
            "Numbers confirm gains [Figure 1].\n\n"
            "## Why It Matters\nThis matters because of practical impact [§4]."
        )
    defaults = dict(
        paper_id="2403.12345",
        title="Test Piece",
        hook="A test hook.",
        content=content,
        word_count=len(content.split()),
        citations=[],
        generated_at="2025-01-01T00:00:00",
        model_used="test",
    )
    defaults.update(kwargs)
    return Piece(**defaults)


class TestCheckBannedWords:
    def test_finds_banned_word(self):
        issues = check_banned_words("This is a revolutionary approach to AI.")
        assert len(issues) >= 1
        assert any(i.issue_type == "banned_word" for i in issues)

    def test_finds_multiple_banned(self):
        issues = check_banned_words("A groundbreaking and revolutionary method.")
        banned = [i for i in issues if i.issue_type == "banned_word"]
        assert len(banned) >= 2

    def test_finds_caution_word(self):
        issues = check_banned_words("This is very important work.")
        caution = [i for i in issues if i.issue_type == "caution_word"]
        assert len(caution) >= 1
        assert caution[0].severity == "warning"

    def test_clean_text(self):
        issues = check_banned_words("The model achieves 90% accuracy on the benchmark.")
        assert len(issues) == 0


class TestCheckStructure:
    def test_all_sections_present(self):
        content = (
            "## The Problem\nProblem text.\n"
            "## What They Did\nApproach text.\n"
            "## The Results\nResults text.\n"
            "## Why It Matters\nImplications text."
        )
        issues = check_structure(content)
        assert len(issues) == 0

    def test_missing_section(self):
        content = "## The Problem\nText.\n## The Results\nResults."
        issues = check_structure(content)
        missing = [i.description for i in issues]
        assert any("What They Did" in m for m in missing)
        assert any("Why It Matters" in m for m in missing)

    def test_all_sections_missing(self):
        content = "Just some random text without any sections."
        issues = check_structure(content)
        assert len(issues) == 4


class TestCheckWordCount:
    def test_within_range(self):
        content = " ".join(["word"] * 1000)
        words, ok = check_word_count(content, StyleConfig())
        assert ok is True
        assert words == 1000

    def test_too_short(self):
        content = " ".join(["word"] * 100)
        words, ok = check_word_count(content, StyleConfig(min_words=800))
        assert ok is False

    def test_too_long(self):
        content = " ".join(["word"] * 2000)
        words, ok = check_word_count(content, StyleConfig(max_words=1200))
        assert ok is False


class TestCheckCitations:
    def test_sufficient_citations(self):
        content = "Claim one [§1]. Claim two [§2.1]. Claim three [Abstract]."
        issues = check_citations(content)
        assert len(issues) == 0

    def test_insufficient_citations(self):
        content = "Text with only one citation [§1]."
        issues = check_citations(content)
        assert len(issues) == 1
        assert "insufficient" in issues[0].issue_type

    def test_no_citations(self):
        content = "No citations at all in this text."
        issues = check_citations(content)
        assert len(issues) == 1


class TestCheckStyleCompliance:
    def test_compliant_piece(self):
        piece = make_piece()
        report = run_async(check_style_compliance(piece))
        assert report.compliant is True

    def test_non_compliant_banned_word(self):
        piece = make_piece(
            content=(
                "## The Problem\nA revolutionary approach [§1].\n"
                "## What They Did\nDetails here [§2]. More info [Table 1].\n"
                "## The Results\nGood results [§3]. Numbers [Figure 1].\n"
                "## Why It Matters\nImplications [§4]."
            )
        )
        report = run_async(check_style_compliance(piece))
        assert report.compliant is False

    def test_strict_mode_warnings_fail(self):
        piece = make_piece(
            content=(
                "## The Problem\nThis is very important [§1].\n"
                "## What They Did\nApproach details [§2]. More [Table 1].\n"
                "## The Results\nResults shown [§3]. Data [Figure 1].\n"
                "## Why It Matters\nImplications [§4]."
            )
        )
        config = StyleConfig(strict_mode=True)
        report = run_async(check_style_compliance(piece, config))
        assert report.compliant is False
