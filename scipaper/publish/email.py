"""
Email delivery for Signal editions via Buttondown API.

Buttondown manages subscribers — this module only creates/sends the email draft.
Hybrid rendering: lead piece in full, secondary pieces as preview with "Read more" link.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import escape
from typing import List, Optional

import httpx

from ..generate.edition import Edition, QuickTake, generate_edition_subject
from ..generate.writer import Piece
from ..retry import api_retry

logger = logging.getLogger(__name__)


@dataclass
class ButtondownConfig:
    """Buttondown API configuration."""
    api_key: Optional[str] = None
    api_url: str = "https://api.buttondown.com"


@dataclass
class DeliveryReport:
    """Report on email delivery to Buttondown."""
    edition_week: str
    sent: bool
    buttondown_id: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    sent_at: Optional[str] = None


# ── HTML Rendering ────────────────────────────────────────────────────


def render_edition_html(edition: Edition, web_base_url: str) -> str:
    """
    Render edition to HTML email.

    Hybrid layout:
    - Lead piece (index 0): rendered in full
    - Secondary pieces (index 1+): hook + first paragraph + "Read more" link
    """
    pieces_html = []
    for i, piece in enumerate(edition.pieces):
        if i == 0:
            pieces_html.append(_render_piece_full_html(piece, is_lead=True))
        else:
            pieces_html.append(_render_piece_preview_html(piece, edition.week, web_base_url))

    quick_takes_html = _render_quick_takes_html(edition.quick_takes)

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
    """Render a piece with full content."""
    title_size = "24px" if is_lead else "20px"
    content_html = _content_to_html(piece.content)

    hero_figure_html = ""
    if is_lead and piece.hero_figure_url:
        caption_html = ""
        if piece.hero_figure_caption:
            caption_html = (
                f'<p style="font-size: 13px; color: #666; margin-top: 8px;">'
                f'{escape(piece.hero_figure_caption)}</p>'
            )
        hero_figure_html = (
            f'<div style="margin: 24px 0;">'
            f'<img src="{escape(piece.hero_figure_url)}" '
            f'alt="{escape(piece.hero_figure_caption or "Key figure from the paper")}" '
            f'style="max-width: 100%; height: auto; border: 2px solid #000; display: block;">'
            f'{caption_html}'
            f'</div>'
        )

    abstract_html = _render_structured_abstract_html(piece)

    return (
        f'<article id="{escape(piece.paper_id)}" style="margin-top: 32px; padding-bottom: 24px; '
        f'border-bottom: 1px solid #eee;">'
        f'<h2 style="font-size: {title_size}; margin-bottom: 4px;">'
        f'{escape(piece.title)}</h2>'
        f'<p style="color: #666; font-style: italic; margin-top: 0;">'
        f'{escape(piece.hook)}</p>'
        f'{abstract_html}'
        f'{hero_figure_html}'
        f'<div style="font-size: 16px;">{content_html}</div>'
        f'</article>'
    )


def _render_piece_preview_html(piece: Piece, week: str, web_base_url: str) -> str:
    """Render a piece as a preview: hook + first paragraph + Read more link."""
    first_paragraph = _extract_first_paragraph(piece.content)
    read_more_url = f"{web_base_url}/editions/{week}.html#{piece.paper_id}"

    abstract_html = _render_structured_abstract_html(piece)

    return (
        f'<article id="{escape(piece.paper_id)}" style="margin-top: 32px; padding-bottom: 24px; '
        f'border-bottom: 1px solid #eee;">'
        f'<h2 style="font-size: 20px; margin-bottom: 4px;">'
        f'{escape(piece.title)}</h2>'
        f'<p style="color: #666; font-style: italic; margin-top: 0;">'
        f'{escape(piece.hook)}</p>'
        f'{abstract_html}'
        f'<div style="font-size: 16px;">'
        f'<p style="margin: 12px 0;">{escape(first_paragraph)}</p>'
        f'</div>'
        f'<p style="margin-top: 12px;">'
        f'<a href="{read_more_url}" style="color: #333; font-weight: 600;">Read more &rarr;</a>'
        f'</p>'
        f'</article>'
    )


def _render_structured_abstract_html(piece: Piece) -> str:
    """Render the structured abstract as inline-styled HTML for email."""
    if not piece.structured_abstract:
        return ""
    sa = piece.structured_abstract
    items = []
    label_style = "font-weight: 700; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; color: #000;"
    for key, label in [
        ("what_they_did", "What they did"),
        ("key_result", "Key result"),
        ("why_it_matters", "Why it matters"),
    ]:
        if sa.get(key):
            items.append(
                f'<li style="margin-bottom: 6px;">'
                f'<span style="{label_style}">{label}</span> &mdash; '
                f'{escape(sa[key])}'
                f'</li>'
            )
    if not items:
        return ""
    return (
        f'<ul style="list-style: none; padding: 0; margin: 0 0 16px; '
        f'font-size: 15px; color: #333;">{"".join(items)}</ul>'
    )


def _extract_first_paragraph(content: str) -> str:
    """Extract the first non-header paragraph from content."""
    paragraphs = content.split("\n\n")
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        # Skip section headers
        if para.startswith("## ") or (para.startswith("**") and para.endswith("**")):
            continue
        return para
    return ""


def _render_quick_takes_html(quick_takes: List[QuickTake]) -> str:
    """Render Quick Takes section to HTML."""
    if not quick_takes:
        return ""

    qt_items = []
    for qt in quick_takes:
        qt_items.append(
            f'<li style="margin-bottom: 12px;">'
            f'<a href="{escape(qt.paper_url)}" style="color: #1a1a1a; '
            f'font-weight: 600; text-decoration: none;">{escape(qt.title)}</a>'
            f'<br><span style="color: #555; font-size: 14px;">{escape(qt.one_liner)}</span>'
            f'</li>'
        )

    return (
        '<div style="margin-top: 40px; padding-top: 24px; border-top: 1px solid #ddd;">'
        '<h2 style="font-size: 20px; color: #333;">Quick Takes</h2>'
        f'<ul style="padding-left: 20px;">{"".join(qt_items)}</ul>'
        '</div>'
    )


def _content_to_html(content: str) -> str:
    """Convert piece content to basic HTML paragraphs."""
    paragraphs = content.split("\n\n")
    html_parts = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        # Check for section headers (## Header or **Header**)
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


# ── Plain Text Rendering ──────────────────────────────────────────────


def render_edition_text(edition: Edition, web_base_url: str) -> str:
    """
    Render edition to plain text.

    Hybrid layout:
    - Lead piece (index 0): rendered in full
    - Secondary pieces (index 1+): hook + first paragraph + "Read more:" link
    """
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

        if piece.structured_abstract:
            sa = piece.structured_abstract
            for key, label in [
                ("what_they_did", "What they did"),
                ("key_result", "Key result"),
                ("why_it_matters", "Why it matters"),
            ]:
                if sa.get(key):
                    lines.append(f"  {label} — {sa[key]}")
            lines.append("")

        if i == 0:
            # Lead: full content
            lines.append(piece.content)
        else:
            # Secondary: first paragraph + read more link
            first_paragraph = _extract_first_paragraph(piece.content)
            if first_paragraph:
                lines.append(first_paragraph)
            lines.append("")
            read_more_url = f"{web_base_url}/editions/{edition.week}.html#{piece.paper_id}"
            lines.append(f"Read more: {read_more_url}")

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


# ── Buttondown API ────────────────────────────────────────────────────


@api_retry
async def _post_to_buttondown(
    api_url: str,
    api_key: str,
    subject: str,
    body: str,
) -> dict:
    """
    POST a draft email to Buttondown. Decorated with api_retry so transient
    network errors (connection refused, timeouts) are retried automatically.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{api_url}/v1/emails",
            headers={
                "Authorization": f"Token {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "subject": subject,
                "body": body,
                "status": "draft",
            },
        )
        response.raise_for_status()
        return response.json()


async def send_edition_email(
    edition: Edition,
    config: ButtondownConfig,
    web_base_url: str,
) -> DeliveryReport:
    """
    Send edition to Buttondown as a draft email.

    Buttondown manages subscribers — no subscriber list needed here.
    Creates a draft via POST /v1/emails with status="draft".

    Returns DeliveryReport with sent=True on success.
    """
    if not config.api_key:
        raise ValueError("ButtondownConfig.api_key is required to send email")

    html = render_edition_html(edition, web_base_url)
    subject = generate_edition_subject(edition)

    errors: List[str] = []
    buttondown_id: Optional[str] = None
    sent = False

    try:
        data = await _post_to_buttondown(
            api_url=config.api_url,
            api_key=config.api_key,
            subject=subject,
            body=html,
        )
        buttondown_id = data.get("id")
        sent = True
        logger.info(
            f"Buttondown email created for {edition.week}: id={buttondown_id}"
        )
    except Exception as e:
        errors.append(str(e))
        logger.error(f"Buttondown email failed for {edition.week}: {e}")

    return DeliveryReport(
        edition_week=edition.week,
        sent=sent,
        buttondown_id=buttondown_id,
        errors=errors,
        sent_at=datetime.now(timezone.utc).isoformat() if sent else None,
    )
