"""
Tests for the email publishing module.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from .conftest import run_async

from scipaper.publish.email import (
    DeliveryReport,
    EmailConfig,
    _content_to_html,
    render_edition_html,
    render_edition_text,
    send_edition_email,
)
from scipaper.generate.edition import Edition, QuickTake
from scipaper.generate.writer import Piece


def make_piece(paper_id="2403.12345", title="Test Piece", hook="A test hook."):
    return Piece(
        paper_id=paper_id,
        title=title,
        hook=hook,
        content="## The Problem\nProblem text.\n\n## What They Did\nApproach text.",
        word_count=8,
        citations=[],
        generated_at="2025-01-01",
        model_used="test",
    )


def make_edition(**kwargs):
    defaults = dict(
        week="2025-W10",
        issue_number=1,
        pieces=[make_piece()],
        quick_takes=[
            QuickTake(
                paper_id="qt1",
                title="Quick Take Paper",
                one_liner="A brief summary.",
                paper_url="https://arxiv.org/abs/qt1",
            )
        ],
        total_words=100,
    )
    defaults.update(kwargs)
    return Edition(**defaults)


class TestRenderEditionHtml:
    def test_contains_header(self):
        edition = make_edition()
        html = render_edition_html(edition)
        assert "Signal" in html
        assert "#1" in html
        assert "2025-W10" in html

    def test_contains_piece(self):
        edition = make_edition()
        html = render_edition_html(edition)
        assert "Test Piece" in html
        assert "A test hook." in html

    def test_contains_quick_takes(self):
        edition = make_edition()
        html = render_edition_html(edition)
        assert "Quick Takes" in html
        assert "Quick Take Paper" in html

    def test_no_quick_takes(self):
        edition = make_edition(quick_takes=[])
        html = render_edition_html(edition)
        assert "Quick Takes" not in html

    def test_valid_html(self):
        edition = make_edition()
        html = render_edition_html(edition)
        assert html.startswith("<!DOCTYPE html>")
        assert "</html>" in html


class TestRenderEditionText:
    def test_contains_header(self):
        edition = make_edition()
        text = render_edition_text(edition)
        assert "SIGNAL" in text
        assert "Issue #1" in text

    def test_contains_piece(self):
        edition = make_edition()
        text = render_edition_text(edition)
        assert "TEST PIECE" in text

    def test_contains_quick_takes(self):
        edition = make_edition()
        text = render_edition_text(edition)
        assert "QUICK TAKES" in text
        assert "Quick Take Paper" in text


class TestContentToHtml:
    def test_paragraphs(self):
        html = _content_to_html("First paragraph.\n\nSecond paragraph.")
        assert "<p" in html
        assert "First paragraph." in html
        assert "Second paragraph." in html

    def test_section_headers(self):
        html = _content_to_html("## The Problem\n\nSome text.")
        assert "<h3" in html
        assert "The Problem" in html

    def test_bold_headers(self):
        html = _content_to_html("**The Problem**\n\nSome text.")
        assert "<h3" in html


class TestSendEditionEmail:
    def test_unknown_provider(self):
        edition = make_edition()
        config = EmailConfig(provider="unknown")
        with pytest.raises(ValueError, match="Unknown email provider"):
            run_async(send_edition_email(edition, ["test@example.com"], config))

    def test_send_via_resend(self):
        edition = make_edition()
        config = EmailConfig(provider="resend", api_key="test-key")

        with patch("scipaper.publish.email._send_via_resend", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = (2, 0, [])
            report = run_async(
                send_edition_email(edition, ["a@example.com", "b@example.com"], config)
            )

        assert report.sent == 2
        assert report.failed == 0

    def test_resend_requires_api_key(self):
        edition = make_edition()
        config = EmailConfig(provider="resend", api_key=None)
        with pytest.raises(ValueError, match="API key"):
            run_async(send_edition_email(edition, ["test@example.com"], config))
