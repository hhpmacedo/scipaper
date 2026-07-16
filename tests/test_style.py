"""
Tests for the style compliance checker.
"""

import json
from unittest.mock import MagicMock, patch

from .conftest import run_async

from scipaper.verify.style import (
    StyleConfig,
    check_banned_words,
    check_word_count,
    check_repeated_hook,
    check_style_compliance,
)
from scipaper.generate.writer import Piece


def _mock_anthropic_client(issues=None):
    """Build a mock anthropic.Anthropic() client returning a canned issues list."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({"issues": issues or []}))]
    mock_client.messages.create.return_value = mock_response
    return mock_client


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


class TestCheckStyleCompliance:
    def test_compliant_piece(self):
        piece = make_piece()
        with patch("scipaper.verify.style.anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value = _mock_anthropic_client()
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
        with patch("scipaper.verify.style.anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value = _mock_anthropic_client()
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
        with patch("scipaper.verify.style.anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value = _mock_anthropic_client()
            report = run_async(check_style_compliance(piece, config))
        assert report.compliant is False


def test_check_repeated_hook_flags_duplicate():
    piece = make_piece(
        hook="Models fail on most tasks.",
        content=(
            "Models fail on most tasks.\n\n"
            "## The Problem\nX [§1].\n\n## What They Did\nY [§2].\n\n"
            "## The Results\nZ [§3].\n\n## Why It Matters\nW [§4]."
        ),
    )
    issue = check_repeated_hook(piece)
    assert issue is not None
    assert issue.severity == "error"
    assert issue.issue_type == "duplicate_hook"


def test_check_repeated_hook_passes_clean():
    piece = make_piece(
        hook="Models fail on most tasks.",
        content=(
            "## The Problem\nX [§1].\n\n## What They Did\nY [§2].\n\n"
            "## The Results\nZ [§3].\n\n## Why It Matters\nW [§4]."
        ),
    )
    assert check_repeated_hook(piece) is None


def test_check_banned_words_still_flags():
    issues = check_banned_words("This is a revolutionary result.")
    assert any(i.issue_type == "banned_word" for i in issues)


def test_check_word_count_reports_ok():
    words, ok = check_word_count("one two three", StyleConfig(min_words=1, max_words=10))
    assert words == 3 and ok is True
