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


@dataclass
class WebConfig:
    """Web archive configuration."""
    output_dir: Path = Path("public")
    site_url: str = "https://signal.hugohmacedo.com"
    site_title: str = "Signal — AI Research for the Curious"
    buttondown_username: str = "signalhhmacedo"


def generate_edition_page(edition: Edition, config: Optional[WebConfig] = None) -> str:
    """
    Generate static HTML page for a single edition.
    """
    config = config or WebConfig()

    pieces_html = []
    for i, piece in enumerate(edition.pieces):
        content_html = _content_to_html(piece.content)
        pieces_html.append(
            f'<article class="piece" id="{escape(piece.paper_id)}">'
            f'<h2>{escape(piece.title)}</h2>'
            f'<p class="hook">{escape(piece.hook)}</p>'
            f'<div class="content">{content_html}</div>'
            f'</article>'
        )

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
            f'<section class="quick-takes">'
            f'<h2>Quick Takes</h2>'
            f'<ul>{"".join(qt_items)}</ul>'
            f'</section>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Signal #{edition.issue_number} — {edition.week}</title>
<link rel="alternate" type="application/rss+xml" title="Signal RSS" href="{config.site_url}/rss.xml">
<link rel="alternate" type="application/json" title="Signal JSON Feed" href="{config.site_url}/feed.json">
<style>
body {{ font-family: Georgia, 'Times New Roman', serif; max-width: 700px; margin: 0 auto; padding: 20px; color: #1a1a1a; line-height: 1.7; }}
header {{ text-align: center; padding: 30px 0; border-bottom: 2px solid #333; }}
header h1 {{ margin: 0; font-size: 32px; }}
header p {{ color: #666; margin: 4px 0 0; }}
.piece {{ margin-top: 40px; padding-bottom: 30px; border-bottom: 1px solid #eee; }}
.piece h2 {{ font-size: 22px; margin-bottom: 4px; }}
.hook {{ color: #555; font-style: italic; margin-top: 0; }}
.quick-takes {{ margin-top: 40px; }}
.quick-takes ul {{ padding-left: 20px; }}
.quick-takes li {{ margin-bottom: 12px; }}
.quick-takes a {{ color: #1a1a1a; font-weight: 600; }}
footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; text-align: center; color: #999; font-size: 13px; }}
nav a {{ color: #333; margin: 0 8px; }}
</style>
</head>
<body>
<header>
<h1><a href="{config.site_url}" style="text-decoration: none; color: inherit;">Signal</a></h1>
<p>AI Research for the Curious &mdash; Issue #{edition.issue_number} &middot; {edition.week}</p>
</header>

{"".join(pieces_html)}

{quick_takes_html}

<footer>
<p>Signal #{edition.issue_number} &middot; {edition.total_words} words &middot; {len(edition.pieces)} pieces</p>
<nav><a href="{config.site_url}">Home</a> <a href="{config.site_url}/archive.html">Archive</a> <a href="{config.site_url}/rss.xml">RSS</a></nav>
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

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape(config.site_title)}</title>
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
<nav><a href="{config.site_url}/archive.html">Archive</a> <a href="{config.site_url}/rss.xml">RSS</a></nav>
</footer>
</body>
</html>"""


def generate_subscribed_page(config: Optional[WebConfig] = None) -> str:
    """
    Generate subscription confirmation page.
    """
    config = config or WebConfig()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Subscribed &mdash; {escape(config.site_title)}</title>
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
</style>
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
<nav><a href="{config.site_url}">Home</a> <a href="{config.site_url}/archive.html">Archive</a> <a href="{config.site_url}/rss.xml">RSS</a></nav>
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
            f'#{ed.issue_number} — {ed.week}</a>'
            f'<span class="lead">{escape(lead_title)}</span>'
            f' &middot; {len(ed.pieces)} pieces, {ed.total_words} words'
            f'</li>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Archive &mdash; {escape(config.site_title)}</title>
<link rel="alternate" type="application/rss+xml" title="Signal RSS" href="{config.site_url}/rss.xml">
<style>
body {{ font-family: Georgia, 'Times New Roman', serif; max-width: 700px; margin: 0 auto; padding: 20px; color: #1a1a1a; line-height: 1.7; }}
header {{ text-align: center; padding: 30px 0; border-bottom: 2px solid #333; }}
header h1 {{ margin: 0; font-size: 32px; }}
header p {{ color: #666; margin: 8px 0 0; }}
.editions {{ list-style: none; padding: 0; }}
.editions li {{ padding: 16px 0; border-bottom: 1px solid #eee; }}
.editions a {{ font-size: 18px; color: #1a1a1a; font-weight: 600; text-decoration: none; }}
.editions .lead {{ display: block; color: #555; font-size: 14px; margin-top: 4px; }}
footer {{ margin-top: 40px; text-align: center; color: #999; font-size: 13px; }}
</style>
</head>
<body>
<header>
<h1>Signal</h1>
<p>AI Research for the Curious &mdash; Archive</p>
</header>

<ul class="editions">
{"".join(edition_items)}
</ul>

<footer>
<nav><a href="{config.site_url}">Home</a> &middot; <a href="{config.site_url}/rss.xml">RSS</a> &middot; <a href="{config.site_url}/feed.json">JSON Feed</a></nav>
</footer>
</body>
</html>"""


# Backward compatibility alias
generate_index_page = generate_archive_page


async def generate_web_archive(
    editions: List[Edition], config: Optional[WebConfig] = None
) -> Path:
    """
    Generate complete static web archive.

    Creates:
    - index.html (landing page with subscribe form)
    - archive.html (edition list)
    - /editions/2025-W10.html (individual editions)
    - /rss.xml (RSS feed)
    - /feed.json (JSON feed)

    Returns path to output directory.
    """
    config = config or WebConfig()
    output = config.output_dir
    output.mkdir(parents=True, exist_ok=True)

    editions_dir = output / "editions"
    editions_dir.mkdir(exist_ok=True)

    # Generate landing page
    landing_html = generate_landing_page(editions, config)
    (output / "index.html").write_text(landing_html)

    # Generate subscribed confirmation page
    subscribed_html = generate_subscribed_page(config)
    (output / "subscribed.html").write_text(subscribed_html)

    # Generate archive
    archive_html = generate_archive_page(editions, config)
    (output / "archive.html").write_text(archive_html)

    # Generate edition pages
    for edition in editions:
        page_html = generate_edition_page(edition, config)
        (editions_dir / f"{edition.week}.html").write_text(page_html)

    # Generate feeds
    rss = generate_rss_feed(editions, config)
    (output / "rss.xml").write_text(rss)

    json_feed = generate_json_feed(editions, config)
    (output / "feed.json").write_text(json_feed)

    logger.info(
        f"Generated web archive: {len(editions)} editions to {output}"
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
