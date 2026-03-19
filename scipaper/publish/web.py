"""
Web archive generation for Signal editions.
"""

import json
import logging
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import List, Optional
from xml.sax.saxutils import escape as xml_escape

from ..generate.edition import Edition
from .email import _content_to_html

logger = logging.getLogger(__name__)


def _og_tags(
    title: str,
    description: str,
    url: str,
    site_name: str = "Signal",
    og_type: str = "website",
    image_url: str = "",
) -> str:
    """Generate Open Graph and Twitter Card meta tags."""
    tags = [
        f'<meta property="og:title" content="{escape(title)}">',
        f'<meta property="og:description" content="{escape(description)}">',
        f'<meta property="og:url" content="{escape(url)}">',
        f'<meta property="og:site_name" content="{escape(site_name)}">',
        f'<meta property="og:type" content="{og_type}">',
        f'<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{escape(title)}">',
        f'<meta name="twitter:description" content="{escape(description)}">',
        f'<meta name="description" content="{escape(description)}">',
    ]
    if image_url:
        tags.append(f'<meta property="og:image" content="{escape(image_url)}">')
        tags.append(f'<meta property="og:image:width" content="1200">')
        tags.append(f'<meta property="og:image:height" content="630">')
        tags.append(f'<meta name="twitter:image" content="{escape(image_url)}">')
    return "\n".join(tags)


PLAUSIBLE_SCRIPT = '<script defer data-domain="signal.hugohmacedo.com" src="https://plausible.io/js/script.js"></script>'


def _generate_og_image(output_path: Path) -> None:
    """Generate a 1200x630 PNG Open Graph image matching the brutalist site design."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.warning("Pillow not installed — skipping OG image generation")
        return

    W, H = 1200, 630
    img = Image.new("RGB", (W, H), "#ffffff")
    draw = ImageDraw.Draw(img)

    # Top rule
    draw.rectangle([0, 0, W, 16], fill="#000000")

    # Load fonts with fallback
    def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
        for path in [
            f"/usr/share/fonts/truetype/dejavu/{name}",
            f"/usr/share/fonts/{name}",
        ]:
            try:
                return ImageFont.truetype(path, size)
            except (OSError, IOError):
                continue
        return ImageFont.load_default()

    font_title = _font("DejaVuSans-Bold.ttf", 100)
    font_subtitle = _font("DejaVuSans.ttf", 26)
    font_body = _font("DejaVuSerif.ttf", 22)
    font_btn = _font("DejaVuSans-Bold.ttf", 15)

    draw.text((80, 160), "SIGNAL", fill="#000000", font=font_title)
    draw.text((80, 300), "AI RESEARCH FOR THE CURIOUS", fill="#000000", font=font_subtitle)
    draw.rectangle([80, 370, 1120, 374], fill="#000000")
    draw.text((80, 410), "Weekly. Grounded in the source. No hype.", fill="#333333", font=font_body)
    draw.rectangle([80, 490, 260, 545], fill="#e63b19")
    draw.text((100, 505), "SUBSCRIBE", fill="#ffffff", font=font_btn)

    img.save(str(output_path), "PNG", optimize=True)
    logger.info(f"Generated OG image: {output_path}")


@dataclass
class WebConfig:
    """Web archive configuration."""
    output_dir: Path = Path("public")
    site_url: str = "https://signal.hugohmacedo.com"
    site_title: str = "Signal — AI Research for the Curious"
    buttondown_username: str = "signalhhmacedo"


MANIFEST_FILE = "editions-manifest.json"


def load_manifest(config: Optional["WebConfig"] = None) -> list:
    """
    Load the editions manifest from public/editions-manifest.json.
    Returns list of dicts with week, issue_number, title, pieces, words.
    """
    config = config or WebConfig()
    path = config.output_dir / MANIFEST_FILE
    if not path.exists():
        return []
    return json.loads(path.read_text())


def save_manifest(entries: list, config: Optional["WebConfig"] = None) -> None:
    """Persist the editions manifest."""
    config = config or WebConfig()
    path = config.output_dir / MANIFEST_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2))


def next_issue_number(config: Optional["WebConfig"] = None) -> int:
    """Return the next issue number based on the manifest."""
    entries = load_manifest(config)
    if not entries:
        return 1
    return max(e["issue_number"] for e in entries) + 1


def append_to_manifest(edition: "Edition", config: Optional["WebConfig"] = None) -> None:
    """Add a new edition entry to the manifest (idempotent by week)."""
    config = config or WebConfig()
    entries = load_manifest(config)
    # Replace if week already exists, otherwise append
    entries = [e for e in entries if e["week"] != edition.week]
    title = edition.pieces[0].title if edition.pieces else edition.week
    entries.append({
        "week": edition.week,
        "issue_number": edition.issue_number,
        "title": title,
        "pieces": len(edition.pieces),
        "words": edition.total_words,
    })
    # Keep sorted by issue number
    entries.sort(key=lambda e: e["issue_number"])
    save_manifest(entries, config)


def generate_edition_page(edition: Edition, config: Optional[WebConfig] = None) -> str:
    """
    Generate static HTML page for a single edition.
    """
    config = config or WebConfig()

    pieces_html = []
    for i, piece in enumerate(edition.pieces):
        content_html = _content_to_html(piece.content)
        paper_url = piece.paper_url or f"https://arxiv.org/abs/{piece.paper_id}"
        title_html = f'<a href="{escape(paper_url)}">{escape(piece.title)}</a>'
        authors_html = ""
        if piece.authors:
            authors_html = f'<p class="authors">{escape(", ".join(piece.authors))}</p>'
        abstract_html = ""
        if piece.structured_abstract:
            sa = piece.structured_abstract
            abstract_items = []
            if sa.get("what_they_did"):
                abstract_items.append(
                    f'<li><strong>What they did</strong> &mdash; {escape(sa["what_they_did"])}</li>'
                )
            if sa.get("key_result"):
                abstract_items.append(
                    f'<li><strong>Key result</strong> &mdash; {escape(sa["key_result"])}</li>'
                )
            if sa.get("why_it_matters"):
                abstract_items.append(
                    f'<li><strong>Why it matters</strong> &mdash; {escape(sa["why_it_matters"])}</li>'
                )
            if abstract_items:
                abstract_html = (
                    f'<ul class="structured-abstract">{"".join(abstract_items)}</ul>'
                )
        hero_figure_html = ""
        if piece.hero_figure_url:
            caption_html = ""
            if piece.hero_figure_caption:
                caption_html = f'<figcaption>{escape(piece.hero_figure_caption)}</figcaption>'
            hero_figure_html = (
                f'<figure class="hero-figure">'
                f'<img src="{escape(piece.hero_figure_url)}" alt="{escape(piece.hero_figure_caption or "Key figure from the paper")}" loading="lazy">'
                f'{caption_html}'
                f'</figure>'
            )
        signal_block_html = ""
        if piece.signal_block and piece.signal_block.strip():
            signal_block_html = (
                f'<aside class="signal-block">'
                f'<span class="signal-block-label">Signal</span>'
                f'{escape(piece.signal_block.strip())}'
                f'</aside>'
            )

        pieces_html.append(
            f'<article class="piece" id="{escape(piece.paper_id)}">'
            f'<h2>{title_html}</h2>'
            f'{authors_html}'
            f'<p class="hook">{escape(piece.hook)}</p>'
            f'{signal_block_html}'
            f'{abstract_html}'
            f'{hero_figure_html}'
            f'<div class="content">{content_html}</div>'
            f'</article>'
        )

    # Table of contents
    toc_items = []
    for i, piece in enumerate(edition.pieces):
        short_title = piece.title
        if len(short_title) > 80:
            short_title = short_title[:77] + "..."
        toc_items.append(
            f'<li><a href="#{escape(piece.paper_id)}">{escape(short_title)}</a></li>'
        )
    if edition.quick_takes:
        toc_items.append(
            f'<li><a href="#quick-takes">Quick Takes ({len(edition.quick_takes)} papers)</a></li>'
        )
    toc_html = (
        f'<nav class="toc">'
        f'<h2>In This Issue</h2>'
        f'<ol>{"".join(toc_items)}</ol>'
        f'</nav>'
    ) if toc_items else ""

    quick_takes_html = ""
    if edition.quick_takes:
        qt_items = []
        for qt in edition.quick_takes:
            qt_items.append(
                f'<li>'
                f'<a href="{escape(qt.paper_url)}">{escape(qt.title)}</a>'
                f'<p>{escape(qt.one_liner)}</p>'
                f'</li>'
            )
        quick_takes_html = (
            f'<section class="quick-takes" id="quick-takes">'
            f'<h2>Quick Takes</h2>'
            f'<ul>{"".join(qt_items)}</ul>'
            f'</section>'
        )

    # Issue summary: one line per piece, derived from signal_block first sentence
    issue_summary_html = ""
    summary_lines = []
    for piece in edition.pieces:
        if piece.signal_block and piece.signal_block.strip():
            # Use the first sentence of the signal block
            first_sentence = piece.signal_block.strip().split(". ")[0]
            if not first_sentence.endswith("."):
                first_sentence += "."
            summary_lines.append(f'<li>{escape(first_sentence)}</li>')
        elif piece.hook:
            summary_lines.append(f'<li>{escape(piece.hook)}</li>')
    if summary_lines:
        issue_summary_html = (
            f'<div class="issue-summary">'
            f'<p class="issue-summary-label">This week in Signal</p>'
            f'<ul>{"".join(summary_lines)}</ul>'
            f'</div>'
        )

    og_description = edition.pieces[0].hook if edition.pieces else "AI research, translated."
    og_title = f"Signal #{edition.issue_number} — {edition.week}"
    og_url = f"{config.site_url}/editions/{edition.week}.html"
    og_image = f"{config.site_url}/og-image.png"
    og = _og_tags(og_title, og_description, og_url, image_url=og_image, og_type="article")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Signal #{edition.issue_number} &mdash; {edition.week}</title>
{og}
<link rel="alternate" type="application/rss+xml" title="Signal RSS" href="{config.site_url}/rss.xml">
<link rel="alternate" type="application/json" title="Signal JSON Feed" href="{config.site_url}/feed.json">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: Georgia, 'Times New Roman', serif; max-width: 720px; margin: 0 auto; padding: 40px 20px; color: #000; line-height: 1.7; }}
.top-rule {{ border: none; border-top: 8px solid #000; margin-bottom: 60px; }}
header {{ padding: 0 0 20px; font-family: "Helvetica Neue", Arial, sans-serif; }}
header h1 {{ font-size: 48px; font-weight: 900; letter-spacing: -2px; text-transform: uppercase; line-height: 0.9; }}
header h1 a {{ text-decoration: none; color: inherit; }}
header p {{ font-size: 14px; font-weight: 400; color: #000; margin-top: 8px; letter-spacing: 1px; text-transform: uppercase; font-family: "Helvetica Neue", Arial, sans-serif; }}
.divider {{ border: none; border-top: 4px solid #000; margin: 0 0 40px; }}
.piece {{ margin-bottom: 40px; padding-bottom: 30px; border-bottom: 2px solid #000; }}
.piece h2 {{ font-family: "Helvetica Neue", Arial, sans-serif; font-size: 24px; font-weight: 900; margin-bottom: 4px; }}
.piece h2 a {{ text-decoration: none; color: inherit; border-bottom: 2px solid #000; }}
.piece h2 a:hover {{ color: #e63b19; border-bottom-color: #e63b19; }}
.piece .authors {{ font-family: "Helvetica Neue", Arial, sans-serif; font-size: 14px; color: #666; margin-bottom: 12px; }}
.hook {{ color: #333; font-style: italic; margin-top: 0; margin-bottom: 16px; }}
.structured-abstract {{ list-style: none; padding: 0; margin: 0 0 20px; font-size: 15px; color: #333; }}
.structured-abstract li {{ margin-bottom: 6px; }}
.structured-abstract strong {{ font-family: "Helvetica Neue", Arial, sans-serif; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; color: #000; }}
.hero-figure {{ margin: 24px 0; }}
.hero-figure img {{ max-width: 100%; height: auto; border: 2px solid #000; display: block; }}
.hero-figure figcaption {{ font-family: "Helvetica Neue", Arial, sans-serif; font-size: 13px; color: #666; margin-top: 8px; }}
.toc {{ margin-bottom: 40px; padding-bottom: 30px; border-bottom: 2px solid #000; }}
.toc h2 {{ font-family: "Helvetica Neue", Arial, sans-serif; font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 12px; }}
.toc ol {{ list-style: none; padding: 0; counter-reset: toc; }}
.toc li {{ counter-increment: toc; margin-bottom: 8px; font-size: 16px; }}
.toc li::before {{ content: counter(toc) ". "; font-family: "Helvetica Neue", Arial, sans-serif; font-weight: 700; }}
.toc a {{ color: #000; text-decoration: none; border-bottom: 1px solid #999; }}
.toc a:hover {{ color: #e63b19; border-bottom-color: #e63b19; }}
.content {{ font-size: 17px; }}
.content p {{ margin-bottom: 14px; }}
.signal-block {{ background: #f5f5f5; border-left: 4px solid #000; padding: 16px 20px; margin: 0 0 24px; font-size: 15px; line-height: 1.6; color: #222; }}
.signal-block-label {{ font-family: "Helvetica Neue", Arial, sans-serif; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; color: #666; display: block; margin-bottom: 6px; }}
.issue-summary {{ margin-bottom: 40px; padding: 20px; border: 3px solid #000; background: #fff; }}
.issue-summary-label {{ font-family: "Helvetica Neue", Arial, sans-serif; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; color: #666; margin-bottom: 12px; }}
.issue-summary ul {{ list-style: none; padding: 0; margin: 0; }}
.issue-summary li {{ font-size: 15px; line-height: 1.5; padding: 8px 0; border-bottom: 1px solid #e0e0e0; color: #222; }}
.issue-summary li:last-child {{ border-bottom: none; }}
.quick-takes {{ margin-top: 40px; padding-top: 30px; border-top: 4px solid #000; }}
.quick-takes h2 {{ font-family: "Helvetica Neue", Arial, sans-serif; font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 20px; }}
.quick-takes ul {{ list-style: none; padding: 0; }}
.quick-takes li {{ margin-bottom: 16px; padding-bottom: 16px; border-bottom: 1px solid #ddd; }}
.quick-takes a {{ color: #000; font-weight: 700; text-decoration: none; border-bottom: 2px solid #000; }}
.quick-takes a:hover {{ color: #e63b19; border-bottom-color: #e63b19; }}
.quick-takes p {{ margin-top: 4px; color: #333; font-size: 15px; }}
.edition-subscribe {{ margin-top: 60px; padding: 40px 0; border-top: 4px solid #000; border-bottom: 4px solid #000; }}
.edition-subscribe h2 {{ font-family: "Helvetica Neue", Arial, sans-serif; font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 8px; }}
.edition-subscribe p {{ font-size: 15px; color: #333; margin-bottom: 16px; }}
.edition-subscribe form {{ display: flex; gap: 0; }}
.edition-subscribe input[type="email"] {{ flex: 1; padding: 14px 16px; font-size: 16px; border: 3px solid #000; border-right: none; font-family: inherit; background: #fff; outline: none; }}
.edition-subscribe input[type="email"]::placeholder {{ color: #999; }}
.edition-subscribe input[type="submit"] {{ padding: 14px 32px; font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; background: #e63b19; color: #fff; border: 3px solid #e63b19; cursor: pointer; font-family: inherit; transition: background 0.15s; }}
.edition-subscribe input[type="submit"]:hover {{ background: #c42f12; border-color: #c42f12; }}
@media (max-width: 480px) {{
  .edition-subscribe form {{ flex-direction: column; }}
  .edition-subscribe input[type="email"] {{ border-right: 3px solid #000; border-bottom: none; }}
  .edition-subscribe input[type="submit"] {{ width: 100%; }}
}}
footer {{ margin-top: 60px; padding-top: 20px; border-top: 2px solid #000; font-family: "Helvetica Neue", Arial, sans-serif; font-size: 13px; text-transform: uppercase; letter-spacing: 1px; }}
footer .meta {{ margin-bottom: 12px; color: #666; }}
footer a {{ color: #000; text-decoration: none; margin-right: 16px; font-weight: 700; }}
footer a:hover {{ color: #e63b19; }}
.copyright {{ margin-top: 12px; font-size: 12px; color: #666; }}
.copyright a {{ color: #666; margin-right: 0; font-weight: 400; }}
.copyright a:hover {{ color: #e63b19; }}
</style>
{PLAUSIBLE_SCRIPT}
</head>
<body>
<hr class="top-rule">
<header>
<h1><a href="{config.site_url}">Signal</a></h1>
<p>Issue #{edition.issue_number} &middot; {edition.week}</p>
</header>

<hr class="divider">

{issue_summary_html}

{toc_html}

{"".join(pieces_html)}

{quick_takes_html}

<div class="edition-subscribe">
<h2>Subscribe &mdash; free</h2>
<p>AI research, translated. Every week.</p>
<form id="edition-subscribe-form">
<input type="email" name="email" id="edition-subscribe-email" placeholder="you@example.com" required>
<input type="submit" value="Subscribe">
</form>
</div>
<script>
document.getElementById('edition-subscribe-form').addEventListener('submit', function(e) {{
  e.preventDefault();
  var email = document.getElementById('edition-subscribe-email').value;
  fetch('https://buttondown.com/api/emails/embed-subscribe/{config.buttondown_username}', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'email=' + encodeURIComponent(email),
    mode: 'no-cors'
  }}).then(function() {{
    window.location.href = '{config.site_url}/subscribed.html';
  }});
}});
</script>

<footer>
<p class="meta">#{edition.issue_number} &middot; {edition.total_words} words &middot; {len(edition.pieces)} pieces</p>
<nav><a href="{config.site_url}">Home</a> <a href="{config.site_url}/archive.html">Archive</a> <a href="{config.site_url}/about.html">About</a> <a href="{config.site_url}/rss.xml">RSS</a></nav>
<p class="copyright">&copy; <a href="https://hugohmacedo.com">Hugo H. Macedo</a></p>
</footer>
</body>
</html>"""


def generate_landing_page(
    editions: List[Edition], config: Optional[WebConfig] = None
) -> str:
    """
    Generate landing page with subscribe form and latest edition link.
    """
    config = config or WebConfig()

    # Latest edition section
    latest_html = ""
    if editions:
        latest = editions[0]
        lead_title = latest.pieces[0].title if latest.pieces else "Latest Edition"
        latest_html = (
            f'<section class="latest">'
            f'<h2>Latest Edition</h2>'
            f'<p><a href="{config.site_url}/editions/{latest.week}.html">'
            f'#{latest.issue_number} — {latest.week}: {escape(lead_title)}</a></p>'
            f'</section>'
        )

    subscribe_url = f"https://buttondown.com/api/emails/embed-subscribe/{config.buttondown_username}"

    og = _og_tags(
        config.site_title,
        "A weekly newsletter that translates AI research papers into clear, rigorous prose. No hype. Every claim grounded in the source.",
        config.site_url,
        image_url=f"{config.site_url}/og-image.png",
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape(config.site_title)}</title>
{og}
<link rel="alternate" type="application/rss+xml" title="Signal RSS" href="{config.site_url}/rss.xml">
<link rel="alternate" type="application/json" title="Signal JSON Feed" href="{config.site_url}/feed.json">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: "Helvetica Neue", Arial, sans-serif; max-width: 720px; margin: 0 auto; padding: 40px 20px; color: #000; line-height: 1.5; }}
.top-rule {{ border: none; border-top: 8px solid #000; margin-bottom: 60px; }}
header {{ padding: 0 0 40px; }}
header h1 {{ font-size: 80px; font-weight: 900; letter-spacing: -3px; text-transform: uppercase; line-height: 0.9; }}
header p {{ font-size: 18px; font-weight: 400; color: #000; margin-top: 8px; letter-spacing: 1px; text-transform: uppercase; }}
.divider {{ border: none; border-top: 4px solid #000; margin: 0 0 40px; }}
.value-prop {{ padding: 0 0 40px; }}
.value-prop p {{ font-size: 20px; font-weight: 400; margin-bottom: 24px; }}
.value-prop .details {{ font-size: 15px; color: #333; }}
.value-prop .details strong {{ color: #000; }}
.subscribe {{ padding: 40px 0; border-top: 4px solid #000; border-bottom: 4px solid #000; margin: 0 0 40px; }}
.subscribe h2 {{ font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 16px; }}
.subscribe form {{ display: flex; gap: 0; }}
.subscribe input[type="email"] {{ flex: 1; padding: 14px 16px; font-size: 16px; border: 3px solid #000; border-right: none; font-family: inherit; background: #fff; outline: none; }}
.subscribe input[type="email"]::placeholder {{ color: #999; }}
.subscribe input[type="submit"] {{ padding: 14px 32px; font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; background: #e63b19; color: #fff; border: 3px solid #e63b19; cursor: pointer; font-family: inherit; transition: background 0.15s; }}
.subscribe input[type="submit"]:hover {{ background: #c42f12; border-color: #c42f12; }}
.latest {{ padding: 0 0 20px; }}
.latest h2 {{ font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; color: #666; margin-bottom: 8px; }}
.latest a {{ color: #000; font-weight: 700; font-size: 18px; text-decoration: none; border-bottom: 2px solid #000; }}
.latest a:hover {{ border-bottom-color: #e63b19; color: #e63b19; }}
footer {{ margin-top: 60px; padding-top: 20px; border-top: 2px solid #000; font-size: 13px; text-transform: uppercase; letter-spacing: 1px; }}
footer a {{ color: #000; text-decoration: none; margin-right: 16px; font-weight: 700; }}
footer a:hover {{ color: #e63b19; }}
@media (max-width: 480px) {{
  header h1 {{ font-size: 52px; letter-spacing: -2px; }}
  .subscribe form {{ flex-direction: column; }}
  .subscribe input[type="email"] {{ border-right: 3px solid #000; border-bottom: none; }}
  .subscribe input[type="submit"] {{ width: 100%; }}
}}
</style>
{PLAUSIBLE_SCRIPT}
</head>
<body>
<hr class="top-rule">
<header>
<h1>Signal</h1>
<p>AI Research for the Curious</p>
</header>

<hr class="divider">

<div class="value-prop">
<p>A weekly newsletter that translates the most important AI research papers into clear, rigorous prose. No hype. No jargon. Every claim grounded in the source.</p>
<p class="details"><strong>3-5 papers</strong> weekly, each 800-1200 words. Written for <strong>engineers, PMs, and founders</strong> who use AI but don't read papers. Delivered <strong>every Tuesday</strong>.</p>
</div>

<div class="subscribe">
<h2>Subscribe &mdash; free</h2>
<form id="subscribe-form">
<input type="email" name="email" id="subscribe-email" placeholder="you@example.com" required>
<input type="submit" value="Subscribe">
</form>
</div>
<script>
document.getElementById('subscribe-form').addEventListener('submit', function(e) {{
  e.preventDefault();
  var email = document.getElementById('subscribe-email').value;
  fetch('{subscribe_url}', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'email=' + encodeURIComponent(email),
    mode: 'no-cors'
  }}).then(function() {{
    window.location.href = '{config.site_url}/subscribed.html';
  }});
}});
</script>

{latest_html}

<footer>
<nav><a href="{config.site_url}/archive.html">Archive</a> <a href="{config.site_url}/about.html">About</a> <a href="{config.site_url}/rss.xml">RSS</a></nav>
<p class="copyright">&copy; <a href="https://hugohmacedo.com">Hugo H. Macedo</a></p>
</footer>
</body>
</html>"""


def generate_subscribed_page(config: Optional[WebConfig] = None) -> str:
    """
    Generate subscription confirmation page.
    """
    config = config or WebConfig()

    og = _og_tags(
        f"Subscribed — {config.site_title}",
        "You're in. AI research, translated. Every Tuesday.",
        f"{config.site_url}/subscribed.html",
        image_url=f"{config.site_url}/og-image.png",
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Subscribed &mdash; {escape(config.site_title)}</title>
{og}
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: "Helvetica Neue", Arial, sans-serif; max-width: 720px; margin: 0 auto; padding: 40px 20px; color: #000; line-height: 1.5; }}
.top-rule {{ border: none; border-top: 8px solid #000; margin-bottom: 60px; }}
header {{ padding: 0 0 40px; }}
header h1 {{ font-size: 80px; font-weight: 900; letter-spacing: -3px; text-transform: uppercase; line-height: 0.9; }}
header p {{ font-size: 18px; font-weight: 400; color: #000; margin-top: 8px; letter-spacing: 1px; text-transform: uppercase; }}
.divider {{ border: none; border-top: 4px solid #000; margin: 0 0 40px; }}
.confirmation {{ padding: 40px 0; }}
.confirmation h2 {{ font-size: 32px; font-weight: 900; margin-bottom: 16px; }}
.confirmation p {{ font-size: 18px; margin-bottom: 12px; color: #333; }}
.confirmation a {{ color: #000; font-weight: 700; border-bottom: 2px solid #000; text-decoration: none; }}
.confirmation a:hover {{ color: #e63b19; border-bottom-color: #e63b19; }}
footer {{ margin-top: 60px; padding-top: 20px; border-top: 2px solid #000; font-size: 13px; text-transform: uppercase; letter-spacing: 1px; }}
footer a {{ color: #000; text-decoration: none; margin-right: 16px; font-weight: 700; }}
footer a:hover {{ color: #e63b19; }}
.copyright {{ margin-top: 12px; font-size: 12px; color: #666; }}
.copyright a {{ color: #666; margin-right: 0; font-weight: 400; }}
.copyright a:hover {{ color: #e63b19; }}
</style>
{PLAUSIBLE_SCRIPT}
</head>
<body>
<hr class="top-rule">
<header>
<h1><a href="{config.site_url}" style="text-decoration:none;color:inherit;">Signal</a></h1>
<p>AI Research for the Curious</p>
</header>

<hr class="divider">

<div class="confirmation">
<h2>You're in.</h2>
<p>Check your inbox for a confirmation email. Your first edition arrives next Tuesday.</p>
<p><a href="{config.site_url}/archive.html">Browse the archive</a> while you wait.</p>
</div>

<footer>
<nav><a href="{config.site_url}">Home</a> <a href="{config.site_url}/archive.html">Archive</a> <a href="{config.site_url}/about.html">About</a> <a href="{config.site_url}/rss.xml">RSS</a></nav>
<p class="copyright">&copy; <a href="https://hugohmacedo.com">Hugo H. Macedo</a></p>
</footer>
</body>
</html>"""


def generate_confirmed_page(config: Optional[WebConfig] = None) -> str:
    """
    Generate the page shown after a subscriber clicks the Buttondown
    confirmation link in their email.
    """
    config = config or WebConfig()

    og = _og_tags(
        f"Confirmed — {config.site_title}",
        "Subscription confirmed. AI research, translated. Every Tuesday.",
        f"{config.site_url}/confirmed.html",
        image_url=f"{config.site_url}/og-image.png",
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Confirmed &mdash; {escape(config.site_title)}</title>
{og}
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: "Helvetica Neue", Arial, sans-serif; max-width: 720px; margin: 0 auto; padding: 40px 20px; color: #000; line-height: 1.5; }}
.top-rule {{ border: none; border-top: 8px solid #000; margin-bottom: 60px; }}
header {{ padding: 0 0 40px; }}
header h1 {{ font-size: 80px; font-weight: 900; letter-spacing: -3px; text-transform: uppercase; line-height: 0.9; }}
header h1 a {{ text-decoration: none; color: inherit; }}
header p {{ font-size: 18px; font-weight: 400; color: #000; margin-top: 8px; letter-spacing: 1px; text-transform: uppercase; }}
.divider {{ border: none; border-top: 4px solid #000; margin: 0 0 40px; }}
.confirmation {{ padding: 40px 0; }}
.confirmation h2 {{ font-size: 32px; font-weight: 900; margin-bottom: 16px; }}
.confirmation p {{ font-size: 18px; margin-bottom: 12px; color: #333; }}
.confirmation a {{ color: #000; font-weight: 700; border-bottom: 2px solid #000; text-decoration: none; }}
.confirmation a:hover {{ color: #e63b19; border-bottom-color: #e63b19; }}
footer {{ margin-top: 60px; padding-top: 20px; border-top: 2px solid #000; font-size: 13px; text-transform: uppercase; letter-spacing: 1px; }}
footer a {{ color: #000; text-decoration: none; margin-right: 16px; font-weight: 700; }}
footer a:hover {{ color: #e63b19; }}
.copyright {{ margin-top: 12px; font-size: 12px; color: #666; }}
.copyright a {{ color: #666; margin-right: 0; font-weight: 400; }}
.copyright a:hover {{ color: #e63b19; }}
</style>
{PLAUSIBLE_SCRIPT}
</head>
<body>
<hr class="top-rule">
<header>
<h1><a href="{config.site_url}">Signal</a></h1>
<p>AI Research for the Curious</p>
</header>

<hr class="divider">

<div class="confirmation">
<h2>Confirmed.</h2>
<p>Your subscription is active. Your first edition arrives next Tuesday.</p>
<p><a href="{config.site_url}/archive.html">Browse the archive</a> while you wait.</p>
</div>

<footer>
<nav><a href="{config.site_url}">Home</a> <a href="{config.site_url}/archive.html">Archive</a> <a href="{config.site_url}/about.html">About</a> <a href="{config.site_url}/rss.xml">RSS</a></nav>
<p class="copyright">&copy; <a href="https://hugohmacedo.com">Hugo H. Macedo</a></p>
</footer>
</body>
</html>"""


def generate_archive_page(
    editions: List[Edition], config: Optional[WebConfig] = None
) -> str:
    """
    Generate archive page listing all editions.
    """
    config = config or WebConfig()

    edition_items = []
    for ed in editions:
        lead_title = ed.pieces[0].title if ed.pieces else "Edition"
        edition_items.append(
            f'<li>'
            f'<a href="{config.site_url}/editions/{ed.week}.html">'
            f'#{ed.issue_number} &mdash; {ed.week}</a>'
            f'<span class="lead">{escape(lead_title)}</span>'
            f'<span class="meta">{len(ed.pieces)} pieces &middot; {ed.total_words} words</span>'
            f'</li>'
        )

    og = _og_tags(
        f"Archive — {config.site_title}",
        "Every edition of Signal. AI research papers, translated into clear prose.",
        f"{config.site_url}/archive.html",
        image_url=f"{config.site_url}/og-image.png",
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Archive &mdash; {escape(config.site_title)}</title>
{og}
<link rel="alternate" type="application/rss+xml" title="Signal RSS" href="{config.site_url}/rss.xml">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: "Helvetica Neue", Arial, sans-serif; max-width: 720px; margin: 0 auto; padding: 40px 20px; color: #000; line-height: 1.5; }}
.top-rule {{ border: none; border-top: 8px solid #000; margin-bottom: 60px; }}
header {{ padding: 0 0 40px; }}
header h1 {{ font-size: 48px; font-weight: 900; letter-spacing: -2px; text-transform: uppercase; line-height: 0.9; }}
header h1 a {{ text-decoration: none; color: inherit; }}
header p {{ font-size: 14px; font-weight: 400; color: #000; margin-top: 8px; letter-spacing: 1px; text-transform: uppercase; }}
.divider {{ border: none; border-top: 4px solid #000; margin: 0 0 40px; }}
.editions {{ list-style: none; padding: 0; }}
.editions li {{ padding: 20px 0; border-bottom: 2px solid #000; }}
.editions a {{ font-size: 18px; color: #000; font-weight: 700; text-decoration: none; border-bottom: 2px solid #000; }}
.editions a:hover {{ color: #e63b19; border-bottom-color: #e63b19; }}
.editions .lead {{ display: block; color: #333; font-size: 15px; margin-top: 6px; }}
.editions .meta {{ color: #666; font-size: 13px; text-transform: uppercase; letter-spacing: 1px; }}
footer {{ margin-top: 60px; padding-top: 20px; border-top: 2px solid #000; font-size: 13px; text-transform: uppercase; letter-spacing: 1px; }}
footer a {{ color: #000; text-decoration: none; margin-right: 16px; font-weight: 700; }}
footer a:hover {{ color: #e63b19; }}
.copyright {{ margin-top: 12px; font-size: 12px; color: #666; }}
.copyright a {{ color: #666; margin-right: 0; font-weight: 400; }}
.copyright a:hover {{ color: #e63b19; }}
</style>
{PLAUSIBLE_SCRIPT}
</head>
<body>
<hr class="top-rule">
<header>
<h1><a href="{config.site_url}">Signal</a></h1>
<p>Archive</p>
</header>

<hr class="divider">

<ul class="editions">
{"".join(edition_items)}
</ul>

<footer>
<nav><a href="{config.site_url}">Home</a> <a href="{config.site_url}/about.html">About</a> <a href="{config.site_url}/rss.xml">RSS</a> <a href="{config.site_url}/feed.json">JSON Feed</a></nav>
<p class="copyright">&copy; <a href="https://hugohmacedo.com">Hugo H. Macedo</a></p>
</footer>
</body>
</html>"""


def generate_about_page(config: Optional[WebConfig] = None) -> str:
    """
    Generate the About / How It Works page.
    """
    config = config or WebConfig()

    og = _og_tags(
        "How It Works — Signal",
        "How Signal finds, writes about, and verifies AI research papers — autonomously, with every claim grounded in the source.",
        f"{config.site_url}/about.html",
        image_url=f"{config.site_url}/og-image.png",
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>How It Works &mdash; Signal</title>
{og}
<link rel="alternate" type="application/rss+xml" title="Signal RSS" href="{config.site_url}/rss.xml">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: Georgia, 'Times New Roman', serif; max-width: 720px; margin: 0 auto; padding: 40px 20px; color: #000; line-height: 1.7; }}
.top-rule {{ border: none; border-top: 8px solid #000; margin-bottom: 60px; }}
header {{ padding: 0 0 20px; font-family: "Helvetica Neue", Arial, sans-serif; }}
header h1 {{ font-size: 48px; font-weight: 900; letter-spacing: -2px; text-transform: uppercase; line-height: 0.9; }}
header h1 a {{ text-decoration: none; color: inherit; }}
header p {{ font-size: 14px; font-weight: 400; color: #000; margin-top: 8px; letter-spacing: 1px; text-transform: uppercase; font-family: "Helvetica Neue", Arial, sans-serif; }}
.divider {{ border: none; border-top: 4px solid #000; margin: 0 0 40px; }}
.about-section {{ margin-bottom: 40px; padding-bottom: 30px; border-bottom: 2px solid #000; }}
.about-section:last-of-type {{ border-bottom: none; }}
.about-section h2 {{ font-family: "Helvetica Neue", Arial, sans-serif; font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 16px; }}
.about-section p {{ font-size: 17px; margin-bottom: 14px; }}
.about-section ul {{ font-size: 17px; margin: 0 0 14px 24px; }}
.about-section li {{ margin-bottom: 8px; }}
.pipeline-step {{ font-family: "Helvetica Neue", Arial, sans-serif; font-weight: 700; }}
footer {{ margin-top: 60px; padding-top: 20px; border-top: 2px solid #000; font-family: "Helvetica Neue", Arial, sans-serif; font-size: 13px; text-transform: uppercase; letter-spacing: 1px; }}
footer a {{ color: #000; text-decoration: none; margin-right: 16px; font-weight: 700; }}
footer a:hover {{ color: #e63b19; }}
.copyright {{ margin-top: 12px; font-size: 12px; color: #666; }}
.copyright a {{ color: #666; margin-right: 0; font-weight: 400; }}
.copyright a:hover {{ color: #e63b19; }}
</style>
{PLAUSIBLE_SCRIPT}
</head>
<body>
<hr class="top-rule">
<header>
<h1><a href="{config.site_url}">Signal</a></h1>
<p>How It Works</p>
</header>

<hr class="divider">

<div class="about-section">
<h2>What This Is</h2>
<p>Signal is a weekly newsletter that translates AI research papers into clear, rigorous prose. Every claim is grounded in the source paper. No hype, no speculation, no &ldquo;this changes everything.&rdquo; Just what the researchers did, what they found, and why it matters.</p>
<p>The entire pipeline &mdash; from finding papers to writing about them to checking the writing against the source &mdash; runs autonomously. This page explains how.</p>
</div>

<div class="about-section">
<h2>How Papers Are Selected</h2>
<p>Each week, the pipeline pulls new papers from ArXiv across four categories: artificial intelligence, machine learning, computational linguistics, and statistical ML. It also checks Semantic Scholar for citation data and scans Hacker News for social signals.</p>
<p>Every paper is scored on two axes:</p>
<ul>
<li><span class="pipeline-step">Relevance</span> &mdash; How important is this paper to the current AI conversation? Scored using keyword matching against a weekly anchor document, institutional signals, citation velocity, and social mentions.</li>
<li><span class="pipeline-step">Narrative potential</span> &mdash; Can we tell a compelling, concrete story about this paper? An LLM evaluates whether the paper has a clear problem, a surprising result, and enough detail to ground an 800&ndash;1200 word piece.</li>
</ul>
<p>The top papers are selected with diversity constraints: no more than two papers from the same institution or topic area. The goal is a well-rounded edition, not a deep dive into one corner of the field.</p>
<p>The only human input in the entire system is a weekly anchor document &mdash; a short list of hot topics, declining topics, and keywords that steer what counts as &ldquo;relevant&rdquo; this week. Everything else is automated.</p>
</div>

<div class="about-section">
<h2>How Papers Are Written</h2>
<p>Each selected paper goes through a three-stage pipeline:</p>
<p><span class="pipeline-step">1. Citation-grounded generation.</span> The full paper is parsed (PDF to text), and an LLM generates an 800&ndash;1200 word piece following a fixed structure: Hook, The Problem, What They Did, The Results, Why It Matters. Every factual claim must cite a specific passage &mdash; a section number, table, figure, or the abstract. If a claim can&rsquo;t be grounded, it doesn&rsquo;t get included.</p>
<p><span class="pipeline-step">2. Adversarial verification.</span> A second LLM reads the draft alongside the original paper and checks each claim against its cited passage. It classifies issues by severity: minor, major, or critical. Types include unsupported claims, overstatements, misrepresentations, and missing context. If any critical issue is found, or three or more major issues, the paper is dropped from the edition entirely &mdash; not patched, dropped.</p>
<p><span class="pipeline-step">3. Style checking.</span> A rule-based pass enforces the style constitution: no banned words (revolutionary, groundbreaking, game-changing), required structure, citation density minimums, and word count limits. This keeps the writing consistent across editions.</p>
</div>

<div class="about-section">
<h2>What You Won&rsquo;t Find Here</h2>
<p>Signal follows a locked style constitution. A few of the rules:</p>
<ul>
<li>The words &ldquo;revolutionary,&rdquo; &ldquo;groundbreaking,&rdquo; &ldquo;breakthrough,&rdquo; and &ldquo;game-changing&rdquo; are banned.</li>
<li>Every piece must include what the paper does <em>not</em> show &mdash; specific limitations, not hand-waving.</li>
<li>No speculation beyond what the paper claims. &ldquo;This could change X&rdquo; only appears if the authors themselves make that argument, and even then it&rsquo;s hedged.</li>
<li>Technical terms are either explained in plain language or avoided.</li>
</ul>
<p>The goal is that after reading a piece, you could explain the paper to a colleague &mdash; accurately, without overselling it.</p>
</div>

<footer>
<nav><a href="{config.site_url}">Home</a> <a href="{config.site_url}/archive.html">Archive</a> <a href="{config.site_url}/about.html">About</a> <a href="{config.site_url}/rss.xml">RSS</a></nav>
<p class="copyright">&copy; <a href="https://hugohmacedo.com">Hugo H. Macedo</a></p>
</footer>
</body>
</html>"""


# Backward compatibility alias
generate_index_page = generate_archive_page


def _stub_edition_from_manifest(entry: dict) -> Edition:
    """Build a minimal Edition from a manifest entry (for archive/feed generation)."""
    from ..generate.writer import Piece
    stub_piece = Piece(
        paper_id="",
        title=entry["title"],
        hook="",
        content="",
        word_count=0,
        citations=[],
        generated_at="",
        model_used="",
    )
    return Edition(
        week=entry["week"],
        issue_number=entry["issue_number"],
        pieces=[stub_piece],
        total_words=entry.get("words", 0),
    )


async def generate_web_archive(
    editions: List[Edition], config: Optional[WebConfig] = None
) -> Path:
    """
    Generate complete static web archive.

    Loads the editions manifest to include all previously published editions
    in the archive, landing page, and feeds — not just the current run.

    Creates:
    - index.html (landing page with subscribe form)
    - archive.html (edition list)
    - /editions/YYYY-WNN.html (individual edition pages)
    - /rss.xml (RSS feed)
    - /feed.json (JSON feed)

    Returns path to output directory.
    """
    config = config or WebConfig()
    output = config.output_dir
    output.mkdir(parents=True, exist_ok=True)

    editions_dir = output / "editions"
    editions_dir.mkdir(exist_ok=True)

    figures_dir = output / "figures"
    figures_dir.mkdir(exist_ok=True)

    # Update manifest with any new editions passed in
    for edition in editions:
        append_to_manifest(edition, config)

    # Load full manifest and build the complete editions list for archive/feeds
    manifest = load_manifest(config)
    new_weeks = {e.week for e in editions}
    all_editions: List[Edition] = []
    for entry in sorted(manifest, key=lambda e: e["issue_number"], reverse=True):
        if entry["week"] in new_weeks:
            # Use the full edition object we just generated
            full = next(e for e in editions if e.week == entry["week"])
            all_editions.append(full)
        else:
            all_editions.append(_stub_edition_from_manifest(entry))

    # Generate landing page (uses latest edition = first in list)
    landing_html = generate_landing_page(all_editions, config)
    (output / "index.html").write_text(landing_html)

    # Generate subscribed confirmation page
    subscribed_html = generate_subscribed_page(config)
    (output / "subscribed.html").write_text(subscribed_html)

    # Generate archive
    archive_html = generate_archive_page(all_editions, config)
    (output / "archive.html").write_text(archive_html)

    # Generate about page
    about_html = generate_about_page(config)
    (output / "about.html").write_text(about_html)

    # Generate edition pages only for new editions (past pages already on disk)
    for edition in editions:
        page_html = generate_edition_page(edition, config)
        (editions_dir / f"{edition.week}.html").write_text(page_html)

    # Generate OG image
    _generate_og_image(output / "og-image.png")

    # Generate email-confirmed page
    confirmed_html = generate_confirmed_page(config)
    (output / "confirmed.html").write_text(confirmed_html)

    # Generate feeds
    rss = generate_rss_feed(all_editions, config)
    (output / "rss.xml").write_text(rss)

    json_feed = generate_json_feed(all_editions, config)
    (output / "feed.json").write_text(json_feed)

    logger.info(
        f"Generated web archive: {len(all_editions)} editions to {output}"
    )

    return output


def generate_rss_feed(
    editions: List[Edition], config: Optional[WebConfig] = None
) -> str:
    """
    Generate RSS 2.0 feed for the archive.
    """
    config = config or WebConfig()

    items = []
    for edition in editions:
        title = f"Signal #{edition.issue_number} — {edition.week}"
        link = f"{config.site_url}/editions/{edition.week}.html"
        desc = ""
        if edition.pieces:
            desc = xml_escape(edition.pieces[0].hook)
        pub_date = ""
        if edition.created_at:
            pub_date = edition.created_at.strftime("%a, %d %b %Y %H:%M:%S +0000")

        items.append(
            f"<item>"
            f"<title>{xml_escape(title)}</title>"
            f"<link>{link}</link>"
            f"<description>{desc}</description>"
            f"<pubDate>{pub_date}</pubDate>"
            f"<guid>{link}</guid>"
            f"</item>"
        )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>{xml_escape(config.site_title)}</title>
<link>{config.site_url}</link>
<description>Weekly AI research newsletter</description>
<language>en-us</language>
{"".join(items)}
</channel>
</rss>"""


def generate_json_feed(
    editions: List[Edition], config: Optional[WebConfig] = None
) -> str:
    """
    Generate JSON Feed (https://jsonfeed.org/) for the archive.
    """
    config = config or WebConfig()

    items = []
    for edition in editions:
        item = {
            "id": f"{config.site_url}/editions/{edition.week}.html",
            "url": f"{config.site_url}/editions/{edition.week}.html",
            "title": f"Signal #{edition.issue_number} — {edition.week}",
        }
        if edition.pieces:
            item["summary"] = edition.pieces[0].hook
        if edition.created_at:
            item["date_published"] = edition.created_at.isoformat()
        items.append(item)

    feed = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": config.site_title,
        "home_page_url": config.site_url,
        "feed_url": f"{config.site_url}/feed.json",
        "items": items,
    }

    return json.dumps(feed, indent=2)
