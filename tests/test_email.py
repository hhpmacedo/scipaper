"""
Tests for the Buttondown email publishing module.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from .conftest import run_async

from scipaper.publish.email import (
    ButtondownConfig,
    _content_to_html,
    render_edition_html,
    render_edition_text,
    send_edition_email,
)
from scipaper.generate.edition import Edition, QuickTake
from scipaper.generate.writer import Piece


def make_piece(
    paper_id="2403.12345",
    title="Test Piece",
    hook="A test hook.",
    content=None,
):
    return Piece(
        paper_id=paper_id,
        title=title,
        hook=hook,
        content=content or "## The Problem\nProblem text.\n\nMore problem text.\n\n## What They Did\nApproach text.",
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


WEB_BASE_URL = "https://signal.example.com"


class TestHybridRendering:
    """Tests for the hybrid HTML rendering: lead full, secondary as preview."""

    def test_lead_piece_rendered_in_full(self):
        """Lead piece (index 0) should render full content."""
        lead = make_piece(paper_id="lead-id", title="Lead Paper", hook="Lead hook.")
        secondary = make_piece(paper_id="sec-id", title="Secondary Paper", hook="Secondary hook.")
        edition = make_edition(pieces=[lead, secondary])

        html = render_edition_html(edition, WEB_BASE_URL)

        # Lead content should be present in full
        assert "Problem text." in html
        assert "Approach text." in html

    def test_secondary_piece_rendered_as_preview(self):
        """Secondary pieces (index 1+) should show hook + first paragraph + 'Read more' link."""
        lead = make_piece(paper_id="lead-id", title="Lead Paper", hook="Lead hook.")
        secondary = make_piece(paper_id="sec-id", title="Secondary Paper", hook="Secondary hook.")
        edition = make_edition(pieces=[lead, secondary])

        html = render_edition_html(edition, WEB_BASE_URL)

        # "Read more" link should appear for secondary
        assert "Read more" in html
        # Link should point to the web archive URL with paper anchor
        assert f"{WEB_BASE_URL}/editions/2025-W10.html#sec-id" in html

    def test_single_piece_rendered_in_full(self):
        """Single piece edition: piece rendered fully, no 'Read more' link."""
        edition = make_edition(pieces=[make_piece(paper_id="only-id")])

        html = render_edition_html(edition, WEB_BASE_URL)

        assert "Problem text." in html
        assert "Read more" not in html

    def test_quick_takes_rendered(self):
        """Quick Takes section should appear with titles and summaries."""
        edition = make_edition()
        html = render_edition_html(edition, WEB_BASE_URL)

        assert "Quick Takes" in html
        assert "Quick Take Paper" in html
        assert "A brief summary." in html

    def test_no_quick_takes(self):
        """Edition with no quick takes should not have Quick Takes section."""
        edition = make_edition(quick_takes=[])
        html = render_edition_html(edition, WEB_BASE_URL)
        assert "Quick Takes" not in html

    def test_header_contains_issue_and_week(self):
        """Header should include Signal branding, issue number, and week."""
        edition = make_edition()
        html = render_edition_html(edition, WEB_BASE_URL)

        assert "Signal" in html
        assert "#1" in html
        assert "2025-W10" in html

    def test_valid_html_structure(self):
        """Output should be valid HTML with DOCTYPE and closing tag."""
        edition = make_edition()
        html = render_edition_html(edition, WEB_BASE_URL)

        assert html.startswith("<!DOCTYPE html>")
        assert "</html>" in html


class TestPlainTextRendering:
    """Tests for the hybrid plain text rendering."""

    def test_header_present(self):
        """Plain text should include SIGNAL header with issue and week."""
        edition = make_edition()
        text = render_edition_text(edition, WEB_BASE_URL)

        assert "SIGNAL" in text
        assert "Issue #1" in text
        assert "2025-W10" in text

    def test_lead_piece_full_content(self):
        """Lead piece content should appear in full in plain text."""
        edition = make_edition(pieces=[make_piece()])
        text = render_edition_text(edition, WEB_BASE_URL)

        assert "TEST PIECE" in text
        assert "Problem text." in text

    def test_secondary_piece_truncated_with_link(self):
        """Secondary pieces should show hook + first paragraph + link in plain text."""
        lead = make_piece(paper_id="lead-id", title="Lead Paper", hook="Lead hook.")
        secondary = make_piece(paper_id="sec-id", title="Secondary Paper", hook="Secondary hook.")
        edition = make_edition(pieces=[lead, secondary])

        text = render_edition_text(edition, WEB_BASE_URL)

        assert "Read more:" in text
        assert f"{WEB_BASE_URL}/editions/2025-W10.html#sec-id" in text

    def test_quick_takes_present(self):
        """Quick Takes section should appear in plain text."""
        edition = make_edition()
        text = render_edition_text(edition, WEB_BASE_URL)

        assert "QUICK TAKES" in text
        assert "Quick Take Paper" in text


class TestButtondownConfig:
    """Tests for ButtondownConfig dataclass."""

    def test_defaults(self):
        """ButtondownConfig should have sensible defaults."""
        config = ButtondownConfig()

        assert config.api_key is None
        assert config.api_url == "https://api.buttondown.com"

    def test_custom_api_key(self):
        """ButtondownConfig should accept api_key."""
        config = ButtondownConfig(api_key="bd_test_key_123")

        assert config.api_key == "bd_test_key_123"
        assert config.api_url == "https://api.buttondown.com"

    def test_custom_api_url(self):
        """ButtondownConfig should accept custom api_url."""
        config = ButtondownConfig(api_key="key", api_url="https://custom.buttondown.com")

        assert config.api_url == "https://custom.buttondown.com"


class TestSendEditionEmail:
    """Tests for send_edition_email Buttondown integration."""

    def test_requires_api_key(self):
        """send_edition_email should raise ValueError if api_key is missing."""
        edition = make_edition()
        config = ButtondownConfig(api_key=None)

        with pytest.raises(ValueError, match="api_key"):
            run_async(send_edition_email(edition, config, WEB_BASE_URL))

    def test_sends_to_buttondown_api(self):
        """send_edition_email should POST to Buttondown /v1/emails endpoint."""
        edition = make_edition()
        config = ButtondownConfig(api_key="bd_test_key")

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "email-abc-123", "status": "draft"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)

            run_async(send_edition_email(edition, config, WEB_BASE_URL))

        # Verify it POSTed to the right endpoint
        call_args = mock_client.post.call_args
        assert "/v1/emails" in call_args[0][0]
        assert call_args[1]["headers"]["Authorization"] == "Token bd_test_key"

        # Verify payload structure
        payload = call_args[1]["json"]
        assert "subject" in payload
        assert "body" in payload
        assert payload["status"] == "draft"

    def test_delivery_report_on_success(self):
        """Successful send should return a DeliveryReport with sent=True."""
        edition = make_edition()
        config = ButtondownConfig(api_key="bd_test_key")

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "email-abc-123"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)

            report = run_async(send_edition_email(edition, config, WEB_BASE_URL))

        assert report.sent is True
        assert report.edition_week == "2025-W10"
        assert report.buttondown_id == "email-abc-123"
        assert report.errors == []
        assert report.sent_at is not None

    def test_handles_api_error(self):
        """API errors should produce a DeliveryReport with sent=False and errors recorded."""
        edition = make_edition()
        config = ButtondownConfig(api_key="bd_test_key")

        import httpx

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=httpx.HTTPStatusError(
                "403 Forbidden",
                request=MagicMock(),
                response=MagicMock(status_code=403),
            ))

            report = run_async(send_edition_email(edition, config, WEB_BASE_URL))

        assert report.sent is False
        assert len(report.errors) > 0


class TestContentToHtml:
    """Tests for the _content_to_html helper (used by web.py too)."""

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
