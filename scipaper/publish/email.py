"""
Email delivery for Signal editions.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional
from html import escape

from ..generate.edition import Edition, QuickTake
from ..generate.writer import Piece

logger = logging.getLogger(__name__)


@dataclass
class EmailConfig:
    """Email delivery configuration."""
    provider: str = "resend"  # resend, postmark, sendgrid
    api_key: Optional[str] = None
    from_email: str = "signal@example.com"
    from_name: str = "Signal"
    reply_to: Optional[str] = None


@dataclass
class DeliveryReport:
    """Report on email delivery."""
    edition_week: str
    total_recipients: int
    sent: int
    failed: int
    errors: List[str]
    sent_at: str


def render_edition_html(edition: Edition) -> str:
    """
    Render edition to HTML email.

    Uses inline CSS for email client compatibility.
    """
    pieces_html = []
    for i, piece in enumerate(edition.pieces):
        piece_html = _render_piece_html(piece, is_lead=(i == 0))
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


def _render_piece_html(piece: Piece, is_lead: bool = False) -> str:
    """Render a single piece to HTML."""
    title_size = "24px" if is_lead else "20px"
    # Convert markdown-ish content to basic HTML
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


def render_edition_text(edition: Edition) -> str:
    """
    Render edition to plain text.

    For email clients that don't support HTML.
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
        lines.append(piece.content)

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
    subscribers: List[str],
    config: Optional[EmailConfig] = None,
) -> DeliveryReport:
    """
    Send edition to all subscribers.

    Returns delivery report.
    """
    config = config or EmailConfig()

    html = render_edition_html(edition)
    plain_text = render_edition_text(edition)

    from ..generate.edition import generate_edition_subject
    subject = generate_edition_subject(edition)

    sent = 0
    failed = 0
    errors = []

    if config.provider == "resend":
        sent, failed, errors = await _send_via_resend(
            html, plain_text, subject, subscribers, config
        )
    elif config.provider == "postmark":
        sent, failed, errors = await _send_via_postmark(
            html, plain_text, subject, subscribers, config
        )
    elif config.provider == "sendgrid":
        sent, failed, errors = await _send_via_sendgrid(
            html, plain_text, subject, subscribers, config
        )
    else:
        raise ValueError(f"Unknown email provider: {config.provider}")

    report = DeliveryReport(
        edition_week=edition.week,
        total_recipients=len(subscribers),
        sent=sent,
        failed=failed,
        errors=errors,
        sent_at=datetime.now(timezone.utc).isoformat(),
    )

    logger.info(
        f"Email delivery for {edition.week}: "
        f"{sent}/{len(subscribers)} sent, {failed} failed"
    )

    return report


async def _send_via_resend(
    html: str,
    plain_text: str,
    subject: str,
    subscribers: List[str],
    config: EmailConfig,
) -> tuple:
    """Send via Resend API."""
    import httpx

    if not config.api_key:
        raise ValueError("Resend API key required")

    sent = 0
    failed = 0
    errors = []

    async with httpx.AsyncClient() as client:
        for email in subscribers:
            try:
                payload = {
                    "from": f"{config.from_name} <{config.from_email}>",
                    "to": [email],
                    "subject": subject,
                    "html": html,
                    "text": plain_text,
                }
                if config.reply_to:
                    payload["reply_to"] = config.reply_to

                response = await client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {config.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                sent += 1
            except Exception as e:
                failed += 1
                errors.append(f"{email}: {e}")
                logger.warning(f"Failed to send to {email}: {e}")

    return sent, failed, errors


async def _send_via_postmark(
    html: str,
    plain_text: str,
    subject: str,
    subscribers: List[str],
    config: EmailConfig,
) -> tuple:
    """Send via Postmark API."""
    import httpx

    if not config.api_key:
        raise ValueError("Postmark API key required")

    sent = 0
    failed = 0
    errors = []

    async with httpx.AsyncClient() as client:
        for email in subscribers:
            try:
                payload = {
                    "From": f"{config.from_name} <{config.from_email}>",
                    "To": email,
                    "Subject": subject,
                    "HtmlBody": html,
                    "TextBody": plain_text,
                    "MessageStream": "broadcast",
                }

                response = await client.post(
                    "https://api.postmarkapp.com/email",
                    headers={
                        "X-Postmark-Server-Token": config.api_key,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                sent += 1
            except Exception as e:
                failed += 1
                errors.append(f"{email}: {e}")

    return sent, failed, errors


async def _send_via_sendgrid(
    html: str,
    plain_text: str,
    subject: str,
    subscribers: List[str],
    config: EmailConfig,
) -> tuple:
    """Send via SendGrid API."""
    import httpx

    if not config.api_key:
        raise ValueError("SendGrid API key required")

    sent = 0
    failed = 0
    errors = []

    async with httpx.AsyncClient() as client:
        for email in subscribers:
            try:
                payload = {
                    "personalizations": [{"to": [{"email": email}]}],
                    "from": {
                        "email": config.from_email,
                        "name": config.from_name,
                    },
                    "subject": subject,
                    "content": [
                        {"type": "text/plain", "value": plain_text},
                        {"type": "text/html", "value": html},
                    ],
                }

                response = await client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={
                        "Authorization": f"Bearer {config.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                sent += 1
            except Exception as e:
                failed += 1
                errors.append(f"{email}: {e}")

    return sent, failed, errors
