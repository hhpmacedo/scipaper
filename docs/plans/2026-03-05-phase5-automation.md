# Phase 5: Automation & Monitoring — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the Signal pipeline run autonomously on a weekly schedule via GitHub Actions, with Buttondown integration, structured logging, failure handling (DEC-004), and retry logic.

**Architecture:** Replace the multi-provider email module with a Buttondown-only integration. Add a top-level CLI entrypoint (`python -m scipaper`) that runs the full pipeline. Implement DEC-005 hybrid email template (lead piece in full, secondary pieces as previews). Add structured JSON logging, tenacity-based retries, and a GitHub Actions weekly workflow. Implement DEC-004 (curate 8-10 papers, Quick Takes fallback, human alert on zero passes).

**Tech Stack:** Python 3.10+, httpx (Buttondown API), tenacity (retries), GitHub Actions (automation), structlog or stdlib logging with JSON formatter

**Decisions referenced:**

- DEC-003: Buttondown as email provider
- DEC-004: Curate 8-10 papers, Quick Takes fallback, alert on 0 passes
- DEC-005: Hybrid email (lead full, secondary preview + link)

---

## Task 1: Rewrite email module for Buttondown API

**Files:**

- Modify: `scipaper/publish/email.py` (full rewrite)
- Modify: `tests/test_email.py` (rewrite tests)
- Modify: `requirements.txt` (remove `resend`, no new dep needed — use httpx)

**Context:**

- Current email.py has three providers (Resend, Postmark, SendGrid) — all being replaced by Buttondown
- Buttondown API: `POST https://api.buttondown.com/v1/emails` with `Authorization: Token <api_key>`
- Buttondown handles subscriber management — no need to pass subscriber list
- Must implement DEC-005: lead piece rendered in full, secondary pieces as hook + first paragraph + "Read more" link

**Step 1: Write failing tests for Buttondown email rendering**

```python
# tests/test_email.py — full rewrite

from unittest.mock import AsyncMock, patch
import pytest
from .conftest import run_async
from scipaper.publish.email import (
    ButtondownConfig,
    DeliveryReport,
    render_edition_html,
    render_edition_text,
    send_edition_email,
)
from scipaper.generate.edition import Edition, QuickTake
from scipaper.generate.writer import Piece


def make_piece(paper_id="2403.12345", title="Test Piece", hook="A test hook.",
               content="## The Problem\nProblem text.\n\n## What They Did\nApproach text."):
    return Piece(
        paper_id=paper_id, title=title, hook=hook, content=content,
        word_count=len(content.split()), citations=[], generated_at="2025-01-01", model_used="test",
    )


def make_edition(**kwargs):
    defaults = dict(
        week="2026-W10", issue_number=1,
        pieces=[make_piece(), make_piece(paper_id="2403.99999", title="Secondary Piece", hook="Another hook.")],
        quick_takes=[QuickTake(paper_id="qt1", title="Quick Take Paper", one_liner="A brief summary.", paper_url="https://arxiv.org/abs/qt1")],
        total_words=100,
    )
    defaults.update(kwargs)
    return Edition(**defaults)


class TestHybridRendering:
    """DEC-005: Lead piece full, secondary pieces as preview."""

    def test_lead_piece_rendered_in_full(self):
        edition = make_edition()
        html = render_edition_html(edition, web_base_url="https://signal.example.com")
        # Lead piece should have full content
        assert "Problem text." in html
        assert "Approach text." in html

    def test_secondary_piece_rendered_as_preview(self):
        edition = make_edition()
        html = render_edition_html(edition, web_base_url="https://signal.example.com")
        # Secondary piece should have hook but truncated content with read more link
        assert "Another hook." in html
        assert "Read more" in html

    def test_single_piece_rendered_in_full(self):
        edition = make_edition(pieces=[make_piece()])
        html = render_edition_html(edition, web_base_url="https://signal.example.com")
        assert "Problem text." in html
        assert "Read more" not in html

    def test_quick_takes_rendered(self):
        edition = make_edition()
        html = render_edition_html(edition, web_base_url="https://signal.example.com")
        assert "Quick Takes" in html
        assert "Quick Take Paper" in html

    def test_contains_header(self):
        edition = make_edition()
        html = render_edition_html(edition, web_base_url="https://signal.example.com")
        assert "Signal" in html
        assert "#1" in html

    def test_valid_html(self):
        edition = make_edition()
        html = render_edition_html(edition, web_base_url="https://signal.example.com")
        assert html.startswith("<!DOCTYPE html>")
        assert "</html>" in html


class TestPlainTextRendering:
    def test_contains_header(self):
        edition = make_edition()
        text = render_edition_text(edition)
        assert "SIGNAL" in text
        assert "Issue #1" in text

    def test_lead_piece_full(self):
        edition = make_edition()
        text = render_edition_text(edition)
        assert "TEST PIECE" in text
        assert "Problem text." in text

    def test_secondary_piece_truncated(self):
        edition = make_edition()
        text = render_edition_text(edition, web_base_url="https://signal.example.com")
        assert "SECONDARY PIECE" in text
        assert "Read more:" in text


class TestButtondownConfig:
    def test_defaults(self):
        config = ButtondownConfig()
        assert config.api_url == "https://api.buttondown.com"
        assert config.api_key is None

    def test_custom_api_key(self):
        config = ButtondownConfig(api_key="test-key")
        assert config.api_key == "test-key"


class TestSendEditionEmail:
    def test_requires_api_key(self):
        edition = make_edition()
        config = ButtondownConfig(api_key=None)
        with pytest.raises(ValueError, match="API key"):
            run_async(send_edition_email(edition, config))

    def test_sends_to_buttondown(self):
        edition = make_edition()
        config = ButtondownConfig(api_key="test-key")

        mock_response = AsyncMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "email-123"}
        mock_response.raise_for_status = lambda: None

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
            report = run_async(send_edition_email(edition, config))

        assert report.sent is True
        assert report.buttondown_id == "email-123"
        mock_post.assert_called_once()

    def test_handles_api_error(self):
        edition = make_edition()
        config = ButtondownConfig(api_key="test-key")

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=Exception("API down")) as mock_post:
            report = run_async(send_edition_email(edition, config))

        assert report.sent is False
        assert len(report.errors) > 0
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_email.py -v`
Expected: FAIL — imports will break because `ButtondownConfig` doesn't exist yet

**Step 3: Implement the Buttondown email module**

```python
# scipaper/publish/email.py — full rewrite

"""
Email delivery for Signal editions via Buttondown.

DEC-003: Buttondown as email provider.
DEC-005: Hybrid rendering — lead piece in full, secondary pieces as preview.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import escape
from typing import List, Optional

from ..generate.edition import Edition, QuickTake
from ..generate.writer import Piece

logger = logging.getLogger(__name__)


@dataclass
class ButtondownConfig:
    """Buttondown API configuration."""
    api_key: Optional[str] = None
    api_url: str = "https://api.buttondown.com"


@dataclass
class DeliveryReport:
    """Report on email delivery."""
    edition_week: str
    sent: bool
    buttondown_id: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    sent_at: Optional[str] = None


def render_edition_html(
    edition: Edition,
    web_base_url: str = "https://signal.example.com",
) -> str:
    """
    Render edition to HTML email.

    DEC-005: Lead piece in full, secondary pieces as preview with "Read more" link.
    """
    pieces_html = []
    for i, piece in enumerate(edition.pieces):
        if i == 0:
            # Lead piece: full content
            piece_html = _render_piece_full_html(piece, is_lead=True)
        else:
            # Secondary pieces: preview only
            piece_html = _render_piece_preview_html(piece, edition.week, web_base_url)
        pieces_html.append(piece_html)

    quick_takes_html = ""
    if edition.quick_takes:
        qt_items = []
        for qt in edition.quick_takes:
            qt_items.append(
                f'<li style="margin-bottom: 12px;">'
                f'<a href="{escape(qt.paper_url)}" style="color: #1a1a1a; '
                f'font-weight: 600; text-decoration: none;">{escape(qt.title)}</a>'
                f'<br><span style="color: #555; font-size: 14px;">{escape(qt.one_liner)}</span>'
                f'</li>'
            )
        quick_takes_html = (
            '<div style="margin-top: 40px; padding-top: 24px; border-top: 1px solid #ddd;">'
            '<h2 style="font-size: 20px; color: #333;">Quick Takes</h2>'
            f'<ul style="padding-left: 20px;">{"".join(qt_items)}</ul>'
            '</div>'
        )

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="font-family: Georgia, 'Times New Roman', serif; max-width: 640px; margin: 0 auto; padding: 20px; color: #1a1a1a; line-height: 1.6;">
<div style="text-align: center; padding: 20px 0; border-bottom: 2px solid #333;">
<h1 style="margin: 0; font-size: 28px;">Signal</h1>
<p style="margin: 4px 0 0; color: #666; font-size: 14px;">AI Research for the Curious &mdash; Issue #{edition.issue_number} &middot; {edition.week}</p>
</div>

{"".join(pieces_html)}

{quick_takes_html}

<div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; text-align: center; color: #999; font-size: 12px;">
<p>Signal #{edition.issue_number} &middot; {edition.total_words} words &middot; {len(edition.pieces)} pieces</p>
</div>
</body>
</html>"""

    return html


def _render_piece_full_html(piece: Piece, is_lead: bool = False) -> str:
    """Render a piece with full content (for lead piece)."""
    title_size = "24px" if is_lead else "20px"
    content_html = _content_to_html(piece.content)

    return (
        f'<article style="margin-top: 32px; padding-bottom: 24px; '
        f'border-bottom: 1px solid #eee;">'
        f'<h2 style="font-size: {title_size}; margin-bottom: 4px;">'
        f'{escape(piece.title)}</h2>'
        f'<p style="color: #666; font-style: italic; margin-top: 0;">'
        f'{escape(piece.hook)}</p>'
        f'<div style="font-size: 16px;">{content_html}</div>'
        f'</article>'
    )


def _render_piece_preview_html(piece: Piece, week: str, web_base_url: str) -> str:
    """Render a piece as preview with hook + first paragraph + read more link."""
    first_para = _extract_first_paragraph(piece.content)
    read_more_url = f"{web_base_url}/editions/{week}.html#{piece.paper_id}"

    return (
        f'<article style="margin-top: 32px; padding-bottom: 24px; '
        f'border-bottom: 1px solid #eee;">'
        f'<h2 style="font-size: 20px; margin-bottom: 4px;">'
        f'{escape(piece.title)}</h2>'
        f'<p style="color: #666; font-style: italic; margin-top: 0;">'
        f'{escape(piece.hook)}</p>'
        f'<p style="font-size: 16px;">{escape(first_para)}</p>'
        f'<a href="{read_more_url}" style="color: #1a73e8; font-weight: 600; '
        f'text-decoration: none;">Read more &rarr;</a>'
        f'</article>'
    )


def _extract_first_paragraph(content: str) -> str:
    """Extract the first non-header paragraph from content."""
    for para in content.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        if para.startswith("## ") or para.startswith("**"):
            continue
        return para
    return content[:200]


def _content_to_html(content: str) -> str:
    """Convert piece content to basic HTML paragraphs."""
    paragraphs = content.split("\n\n")
    html_parts = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if para.startswith("## "):
            header = escape(para[3:])
            html_parts.append(
                f'<h3 style="font-size: 18px; margin-top: 24px;">{header}</h3>'
            )
        elif para.startswith("**") and para.endswith("**"):
            header = escape(para.strip("*"))
            html_parts.append(
                f'<h3 style="font-size: 18px; margin-top: 24px;">{header}</h3>'
            )
        else:
            html_parts.append(f'<p style="margin: 12px 0;">{escape(para)}</p>')
    return "".join(html_parts)


def render_edition_text(
    edition: Edition,
    web_base_url: str = "https://signal.example.com",
) -> str:
    """Render edition to plain text (DEC-005 hybrid)."""
    lines = []
    lines.append("=" * 50)
    lines.append("SIGNAL — AI Research for the Curious")
    lines.append(f"Issue #{edition.issue_number} · {edition.week}")
    lines.append("=" * 50)
    lines.append("")

    for i, piece in enumerate(edition.pieces):
        if i > 0:
            lines.append("")
            lines.append("-" * 40)
            lines.append("")

        lines.append(piece.title.upper())
        lines.append("")
        lines.append(piece.hook)
        lines.append("")

        if i == 0:
            # Lead piece: full content
            lines.append(piece.content)
        else:
            # Secondary: first paragraph + link
            first_para = _extract_first_paragraph(piece.content)
            lines.append(first_para)
            lines.append("")
            lines.append(f"Read more: {web_base_url}/editions/{edition.week}.html#{piece.paper_id}")

    if edition.quick_takes:
        lines.append("")
        lines.append("-" * 40)
        lines.append("QUICK TAKES")
        lines.append("-" * 40)
        lines.append("")
        for qt in edition.quick_takes:
            lines.append(f"• {qt.title}")
            lines.append(f"  {qt.one_liner}")
            lines.append(f"  {qt.paper_url}")
            lines.append("")

    lines.append("=" * 50)
    lines.append(
        f"Signal #{edition.issue_number} · "
        f"{edition.total_words} words · "
        f"{len(edition.pieces)} pieces"
    )

    return "\n".join(lines)


async def send_edition_email(
    edition: Edition,
    config: ButtondownConfig,
    web_base_url: str = "https://signal.example.com",
) -> DeliveryReport:
    """
    Send edition via Buttondown API.

    Buttondown manages subscribers — we just push the email content.
    """
    if not config.api_key:
        raise ValueError("Buttondown API key required")

    import httpx
    from ..generate.edition import generate_edition_subject

    subject = generate_edition_subject(edition)
    html = render_edition_html(edition, web_base_url=web_base_url)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{config.api_url}/v1/emails",
                headers={
                    "Authorization": f"Token {config.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "subject": subject,
                    "body": html,
                    "status": "draft",  # Create as draft first for safety
                },
            )
            response.raise_for_status()
            data = response.json()

        report = DeliveryReport(
            edition_week=edition.week,
            sent=True,
            buttondown_id=data.get("id"),
            sent_at=datetime.now(timezone.utc).isoformat(),
        )
        logger.info(f"Email created in Buttondown: {report.buttondown_id}")

    except Exception as e:
        report = DeliveryReport(
            edition_week=edition.week,
            sent=False,
            errors=[str(e)],
        )
        logger.error(f"Buttondown delivery failed: {e}")

    return report
```

**Step 4: Update requirements.txt**

Remove `resend>=0.7.0` line (no longer needed — httpx is already a dependency).

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_email.py -v`
Expected: All tests PASS

**Step 6: Update pipeline.py imports**

Update `PipelineConfig` to use `ButtondownConfig` instead of `EmailConfig`. Update `send_edition_email` call signature (no longer takes subscriber list).

In `scipaper/pipeline.py`:

- Replace `from .publish.email import DeliveryReport, EmailConfig, send_edition_email` with `from .publish.email import ButtondownConfig, DeliveryReport, send_edition_email`
- Change `PipelineConfig.email` type from `Optional[EmailConfig]` to `Optional[ButtondownConfig]`
- Add `web_base_url: str = "https://signal.example.com"` to `PipelineConfig`
- Update the email sending block: remove `subscribers` parameter, add `web_base_url`
- Remove the `subscribers` parameter from `run_pipeline()`

**Step 7: Update pipeline tests**

Update `tests/test_pipeline.py` to match new `send_edition_email` signature (no subscriber list).

**Step 8: Run full test suite**

Run: `pytest -v`
Expected: All 155+ tests pass (some test counts will change due to rewritten email tests)

**Step 9: Commit**

```bash
git add scipaper/publish/email.py tests/test_email.py scipaper/pipeline.py tests/test_pipeline.py requirements.txt
git commit -m "feat: replace multi-provider email with Buttondown API (DEC-003, DEC-005)

Implement hybrid email rendering: lead piece in full, secondary pieces
as preview with 'Read more' link to web archive. Replace Resend/Postmark/
SendGrid with Buttondown API integration."
```

---

## Task 2: Add top-level CLI entrypoint

**Files:**

- Create: `scipaper/__main__.py`
- Test: `tests/test_cli.py`

**Context:**

- Currently only `python -m scipaper.curate` exists
- Need `python -m scipaper` to run the full pipeline (used by GitHub Actions)
- Should load anchor document, run full pipeline, and report results

**Step 1: Write failing test for CLI**

```python
# tests/test_cli.py

from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from .conftest import run_async


class TestMainCLI:
    def test_imports(self):
        """CLI module can be imported."""
        from scipaper.__main__ import main
        assert callable(main)

    def test_run_command_calls_pipeline(self):
        """--run triggers the full pipeline."""
        from scipaper.__main__ import cmd_run_pipeline

        mock_result = MagicMock()
        mock_result.papers_ingested = 10
        mock_result.papers_selected = 5
        mock_result.pieces_generated = 3
        mock_result.pieces_passed = 3
        mock_result.edition = MagicMock()
        mock_result.edition.week = "2026-W10"
        mock_result.errors = []

        with patch("scipaper.__main__.run_pipeline", new_callable=AsyncMock, return_value=mock_result):
            with patch("scipaper.__main__.load_anchor") as mock_anchor:
                mock_anchor.return_value = MagicMock()
                # Should not raise
                run_async(cmd_run_pipeline(MagicMock(week=None, log_level="INFO")))
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL — `scipaper/__main__.py` doesn't exist

**Step 3: Implement the CLI**

```python
# scipaper/__main__.py

"""
CLI for the full Signal pipeline.

Usage:
    python -m scipaper --run              # Run full pipeline
    python -m scipaper --run --week 2026-W10  # Run for specific week
"""

import argparse
import asyncio
import logging
import sys

from .curate.__main__ import load_anchor, setup_logging
from .pipeline import PipelineConfig, run_pipeline
from .publish.email import ButtondownConfig
from .publish.web import WebConfig


logger = logging.getLogger("scipaper")


async def cmd_run_pipeline(args):
    """Run the full Signal pipeline."""
    anchor = load_anchor(getattr(args, "week", None))

    config = PipelineConfig(
        week=anchor.week,
        email=ButtondownConfig(api_key=_get_env("BUTTONDOWN_API_KEY", required=False)),
        web=WebConfig(),
        web_base_url=_get_env("SIGNAL_WEB_URL", default="https://signal.example.com"),
    )

    result = await run_pipeline(anchor, config)

    # Report
    print(f"\n{'=' * 50}")
    print(f"Signal Pipeline — {result.edition.week if result.edition else 'N/A'}")
    print(f"{'=' * 50}")
    print(f"Papers ingested:  {result.papers_ingested}")
    print(f"Papers selected:  {result.papers_selected}")
    print(f"Pieces generated: {result.pieces_generated}")
    print(f"Pieces passed:    {result.pieces_passed}")

    if result.edition:
        print(f"Edition pieces:   {len(result.edition.pieces)}")
        print(f"Total words:      {result.edition.total_words}")

    if result.errors:
        print(f"\nErrors ({len(result.errors)}):")
        for err in result.errors:
            print(f"  - {err}")

    if result.pieces_passed == 0:
        logger.error("No pieces passed verification — no edition published")
        sys.exit(1)

    return result


def _get_env(key: str, default: str = "", required: bool = False) -> str:
    """Get environment variable."""
    import os
    value = os.environ.get(key, default)
    if required and not value:
        logger.error(f"Required environment variable {key} not set")
        sys.exit(1)
    return value


def main():
    parser = argparse.ArgumentParser(
        description="Signal — AI Research Newsletter Pipeline",
        prog="python -m scipaper",
    )
    parser.add_argument("--run", action="store_true", help="Run full pipeline")
    parser.add_argument("--week", type=str, default=None, help="Anchor document week (e.g., 2026-W10)")
    parser.add_argument("--log-level", type=str, default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    args = parser.parse_args()
    setup_logging(args.log_level)

    if args.run:
        asyncio.run(cmd_run_pipeline(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
```

**Step 4: Run tests**

Run: `pytest tests/test_cli.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scipaper/__main__.py tests/test_cli.py
git commit -m "feat: add top-level CLI entrypoint (python -m scipaper --run)"
```

---

## Task 3: Implement DEC-004 failure handling

**Files:**

- Modify: `scipaper/pipeline.py`
- Modify: `tests/test_pipeline.py`

**Context:**

- DEC-004: Curate 8-10 papers (not 5), Quick Takes fallback if <3 pass, alert on 0
- Current `SelectionConfig.target_count` defaults to 5 — change to 8
- Pipeline needs logic for: thin edition → Quick Takes only, zero edition → exit code 1

**Step 1: Write failing tests for failure handling**

```python
# Add to tests/test_pipeline.py

class TestDEC004FailureHandling:
    """DEC-004: Curate 8-10 papers, Quick Takes fallback, alert on zero."""

    def test_default_target_count_is_8(self):
        """DEC-004: Default selection targets 8 papers for buffer."""
        config = PipelineConfig()
        assert config.selection.target_count == 8

    def test_thin_edition_produces_quick_takes_only(self, tmp_path):
        """When <3 pieces pass, edition uses Quick Takes format."""
        # ... test that result.edition exists but uses Quick Takes for failed pieces
        pass

    def test_zero_passes_returns_no_edition(self):
        """When 0 pieces pass, no edition is produced."""
        # This is already tested by test_pipeline_rejects_bad_verification
        # but we add an explicit assertion about the result
        pass
```

**Step 2: Update SelectionConfig default**

In `scipaper/curate/select.py`, change `SelectionConfig.target_count` default from `5` to `8`.

**Step 3: Update PipelineConfig defaults**

In `scipaper/pipeline.py`, ensure `SelectionConfig(target_count=8)` is the default.

**Step 4: Run tests**

Run: `pytest tests/test_pipeline.py tests/test_select.py -v`
Expected: PASS (some existing tests may need target_count override)

**Step 5: Commit**

```bash
git add scipaper/curate/select.py scipaper/pipeline.py tests/test_pipeline.py tests/test_select.py
git commit -m "feat: implement DEC-004 failure handling (curate 8-10 papers buffer)"
```

---

## Task 4: Add tenacity retry logic to external API calls

**Files:**

- Modify: `scipaper/curate/ingest.py` (ArXiv API retries)
- Modify: `scipaper/curate/score.py` (LLM API retries)
- Modify: `scipaper/generate/writer.py` (LLM API retries)
- Modify: `scipaper/verify/checker.py` (LLM API retries)
- Modify: `scipaper/publish/email.py` (Buttondown API retries)
- Test: existing tests should still pass (retries are transparent)

**Context:**

- `tenacity` is already in `requirements.txt`
- Retry on transient errors: connection errors, 429 (rate limit), 500-503
- Use exponential backoff: wait 1s, 2s, 4s, max 3 retries
- Log retry attempts

**Step 1: Create a shared retry decorator**

```python
# Add to scipaper/config/__init__.py (or create scipaper/retry.py)

import logging
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

logger = logging.getLogger(__name__)


def api_retry(func):
    """Retry decorator for external API calls.

    Retries on connection errors and HTTP 429/5xx with exponential backoff.
    """
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )(func)
```

**Step 2: Apply retry decorator to LLM API functions**

In `scipaper/curate/score.py`, wrap `_score_with_anthropic` and `_score_with_openai` with `@api_retry`.

In `scipaper/generate/writer.py`, wrap `_generate_with_anthropic` and `_generate_with_openai` with `@api_retry`.

In `scipaper/verify/checker.py`, wrap `_verify_with_anthropic` and `_verify_with_openai` with `@api_retry`.

In `scipaper/publish/email.py`, wrap the httpx call inside `send_edition_email` with retry.

**Step 3: Write a simple test for the retry helper**

```python
# tests/test_retry.py

from unittest.mock import MagicMock
import pytest
from scipaper.retry import api_retry


class TestApiRetry:
    def test_succeeds_on_first_try(self):
        call_count = 0

        @api_retry
        def succeed():
            nonlocal call_count
            call_count += 1
            return "ok"

        assert succeed() == "ok"
        assert call_count == 1

    def test_retries_on_connection_error(self):
        call_count = 0

        @api_retry
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("connection reset")
            return "ok"

        assert flaky() == "ok"
        assert call_count == 3

    def test_gives_up_after_max_retries(self):
        @api_retry
        def always_fails():
            raise ConnectionError("down")

        with pytest.raises(ConnectionError):
            always_fails()
```

**Step 4: Run tests**

Run: `pytest tests/test_retry.py -v && pytest -v`
Expected: All pass

**Step 5: Commit**

```bash
git add scipaper/retry.py scipaper/curate/score.py scipaper/generate/writer.py scipaper/verify/checker.py scipaper/publish/email.py tests/test_retry.py
git commit -m "feat: add tenacity retry logic for external API calls"
```

---

## Task 5: Add structured logging

**Files:**

- Modify: `scipaper/pipeline.py` (add structured log data)
- Modify: `scipaper/__main__.py` (JSON log formatter option)
- Test: manual verification (logging changes don't need unit tests)

**Context:**

- Use stdlib logging with a JSON formatter for GitHub Actions
- Add key metrics to log messages: paper counts, scores, timing
- Keep human-readable format for local dev, JSON for CI

**Step 1: Add JSON log formatter**

```python
# Add to scipaper/__main__.py setup_logging

import json as json_module
import time


class JSONFormatter(logging.Formatter):
    """JSON log formatter for CI/CD environments."""
    def format(self, record):
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "metrics"):
            log_data["metrics"] = record.metrics
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json_module.dumps(log_data)
```

**Step 2: Add `--json-logs` flag to CLI**

In `scipaper/__main__.py`, add `--json-logs` argument. When set, use `JSONFormatter` instead of the default formatter.

**Step 3: Add timing to pipeline stages**

In `scipaper/pipeline.py`, add `time.time()` around each stage and log the duration:

```python
import time
# At start of each stage:
stage_start = time.time()
# At end:
logger.info(f"Stage 1 complete in {time.time() - stage_start:.1f}s")
```

**Step 4: Run full test suite**

Run: `pytest -v`
Expected: All pass

**Step 5: Commit**

```bash
git add scipaper/__main__.py scipaper/pipeline.py
git commit -m "feat: add structured JSON logging and pipeline timing"
```

---

## Task 6: Create GitHub Actions workflow

**Files:**

- Create: `.github/workflows/weekly-edition.yml`
- Create: `.github/workflows/test.yml`

**Context:**

- Weekly cron: Sundays at 18:00 UTC (gives time for review before Tuesday send)
- Manual trigger for testing
- Needs secrets: `ANTHROPIC_API_KEY`, `BUTTONDOWN_API_KEY`
- Also needs a test CI workflow for PRs

**Step 1: Create the test workflow**

```yaml
# .github/workflows/test.yml
name: Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: pytest -v
      - run: ruff check .
```

**Step 2: Create the weekly edition workflow**

```yaml
# .github/workflows/weekly-edition.yml
name: Weekly Edition

on:
  schedule:
    - cron: "0 18 * * 0" # Sundays 18:00 UTC
  workflow_dispatch:
    inputs:
      week:
        description: "Anchor week override (e.g., 2026-W10)"
        required: false

jobs:
  generate:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run pipeline
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          BUTTONDOWN_API_KEY: ${{ secrets.BUTTONDOWN_API_KEY }}
          SIGNAL_WEB_URL: ${{ secrets.SIGNAL_WEB_URL }}
        run: |
          python -m scipaper --run \
            ${{ github.event.inputs.week && format('--week {0}', github.event.inputs.week) || '' }} \
            --json-logs

      - name: Upload web archive
        if: success()
        uses: actions/upload-artifact@v4
        with:
          name: web-archive
          path: public/

      - name: Notify on failure
        if: failure()
        uses: actions/github-script@v7
        with:
          script: |
            await github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: `Pipeline failure: ${new Date().toISOString().split('T')[0]}`,
              body: `Weekly pipeline failed. Check [workflow run](${context.serverUrl}/${context.repo.owner}/${context.repo.repo}/actions/runs/${context.runId}).`,
              labels: ['pipeline-failure'],
            });
```

**Step 3: Commit**

```bash
git add .github/workflows/test.yml .github/workflows/weekly-edition.yml
git commit -m "feat: add GitHub Actions for CI tests and weekly pipeline (Phase 5)"
```

---

## Task 7: Create ops runbook

**Files:**

- Create: `docs/RUNBOOK.md`

**Context:**

- Document how to manually trigger pipeline, debug failures, handle edge cases
- Reference DEC-004 escalation procedure

**Step 1: Write the runbook**

```markdown
# Signal Operations Runbook

## Weekly Pipeline

The pipeline runs automatically every Sunday at 18:00 UTC via GitHub Actions.

### Manual Trigger

1. Go to Actions tab in GitHub
2. Select "Weekly Edition" workflow
3. Click "Run workflow"
4. Optionally specify a week override (e.g., `2026-W10`)

### Local Run

    export ANTHROPIC_API_KEY=...
    export BUTTONDOWN_API_KEY=...
    python -m scipaper --run --week 2026-W10

## Failure Handling (DEC-004)

| Scenario                     | Pipeline Behavior                        | Human Action                                    |
| ---------------------------- | ---------------------------------------- | ----------------------------------------------- |
| 1-2 papers fail verification | Dropped, edition proceeds with remaining | None                                            |
| <3 papers pass               | Quick Takes edition published            | Review why papers failed                        |
| 0 papers pass                | Pipeline exits with error, no edition    | Review within 24h, manually re-run or skip week |
| >20% weekly failure rate     | Logged as warning                        | Investigate prompt/model issues                 |

## Common Issues

### "No anchor documents found"

Create an anchor file in `data/anchors/<week>.yaml`. See existing files for format.

### "Buttondown API key required"

Set `BUTTONDOWN_API_KEY` environment variable or GitHub secret.

### Pipeline times out (>30 min)

- Check if ArXiv API is slow (retry usually helps)
- Check if LLM API is rate-limited
- Reduce `max_papers` in IngestConfig

### Verification rejects everything

- Check if the paper full text was extracted properly
- Try running generation on a single paper: `python -m scipaper.curate --fetch && python -m scipaper --run --week <week>`
- Review verification prompts for overly strict criteria

## Monitoring

- GitHub Actions sends failure notifications via issue creation
- Check pipeline logs: Actions tab → Weekly Edition → latest run → "Run pipeline" step
- JSON logs available when `--json-logs` flag is used
```

**Step 2: Commit**

```bash
git add docs/RUNBOOK.md
git commit -m "docs: add operations runbook for weekly pipeline"
```

---

## Task 8: Update web.py for piece anchors (DEC-005 support)

**Files:**

- Modify: `scipaper/publish/web.py`
- Modify: `tests/test_web.py`

**Context:**

- DEC-005 email previews link to `web_base_url/editions/{week}.html#{paper_id}`
- Web archive edition pages need `id` attributes on article elements for anchor links

**Step 1: Write failing test**

```python
# Add to tests/test_web.py

def test_edition_page_has_piece_anchors(self):
    """Pieces have id attributes for DEC-005 anchor links."""
    edition = make_edition()
    html = generate_edition_page(edition)
    assert 'id="2403.12345"' in html
```

**Step 2: Update generate_edition_page**

In `scipaper/publish/web.py`, add `id="{piece.paper_id}"` to each article element:

```python
f'<article class="piece" id="{escape(piece.paper_id)}">'
```

**Step 3: Run tests**

Run: `pytest tests/test_web.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add scipaper/publish/web.py tests/test_web.py
git commit -m "feat: add piece anchor IDs to web archive for DEC-005 email links"
```

---

## Task 9: Final integration test and full suite run

**Files:**

- None new — just verify everything works together

**Step 1: Run full test suite**

Run: `pytest -v`
Expected: All tests pass

**Step 2: Run linter**

Run: `ruff check .`
Expected: No errors

**Step 3: Verify CLI works**

Run: `python -m scipaper --help`
Expected: Shows help text with `--run`, `--week`, `--json-logs` options

**Step 4: Final commit (if any fixes needed)**

```bash
git commit -m "fix: address issues found in Phase 5 integration testing"
```

---

## Summary of changes

| File                                   | Action  | Purpose                                   |
| -------------------------------------- | ------- | ----------------------------------------- |
| `scipaper/publish/email.py`            | Rewrite | Buttondown API + DEC-005 hybrid rendering |
| `scipaper/__main__.py`                 | Create  | Top-level CLI + JSON logging              |
| `scipaper/retry.py`                    | Create  | Shared retry decorator                    |
| `scipaper/pipeline.py`                 | Modify  | Buttondown config, timing, DEC-004        |
| `scipaper/curate/select.py`            | Modify  | Default target_count=8 (DEC-004)          |
| `scipaper/publish/web.py`              | Modify  | Piece anchor IDs                          |
| `tests/test_email.py`                  | Rewrite | Buttondown + hybrid rendering tests       |
| `tests/test_cli.py`                    | Create  | CLI tests                                 |
| `tests/test_retry.py`                  | Create  | Retry logic tests                         |
| `tests/test_pipeline.py`               | Modify  | Updated for new config                    |
| `tests/test_web.py`                    | Modify  | Anchor ID test                            |
| `.github/workflows/test.yml`           | Create  | CI test workflow                          |
| `.github/workflows/weekly-edition.yml` | Create  | Weekly pipeline automation                |
| `docs/RUNBOOK.md`                      | Create  | Operations runbook                        |
| `requirements.txt`                     | Modify  | Remove resend dependency                  |
