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
    buttondown_username: str = "signal"


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
<nav><a href="{config.site_url}">Archive</a> <a href="{config.site_url}/rss.xml">RSS</a></nav>
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
body {{ font-family: Georgia, 'Times New Roman', serif; max-width: 700px; margin: 0 auto; padding: 20px; color: #1a1a1a; line-height: 1.7; }}
header {{ text-align: center; padding: 60px 0 40px; }}
header h1 {{ margin: 0; font-size: 48px; letter-spacing: -1px; }}
header p {{ color: #555; margin: 8px 0 0; font-size: 18px; }}
.value-prop {{ max-width: 540px; margin: 0 auto; padding: 20px 0; }}
.value-prop ul {{ padding-left: 20px; }}
.value-prop li {{ margin-bottom: 8px; }}
.subscribe {{ text-align: center; padding: 40px 0; border-top: 1px solid #eee; border-bottom: 1px solid #eee; margin: 30px 0; }}
.subscribe h2 {{ font-size: 22px; margin-bottom: 16px; }}
.subscribe form {{ display: flex; justify-content: center; gap: 8px; flex-wrap: wrap; }}
.subscribe input[type="email"] {{ padding: 10px 16px; font-size: 16px; border: 1px solid #ccc; border-radius: 4px; width: 280px; font-family: inherit; }}
.subscribe input[type="submit"] {{ padding: 10px 24px; font-size: 16px; background: #1a1a1a; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-family: inherit; }}
.subscribe input[type="submit"]:hover {{ background: #333; }}
.latest {{ text-align: center; padding: 20px 0; }}
.latest h2 {{ font-size: 18px; color: #666; margin-bottom: 8px; }}
.latest a {{ color: #1a1a1a; font-weight: 600; text-decoration: none; }}
.latest a:hover {{ text-decoration: underline; }}
footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; text-align: center; color: #999; font-size: 13px; }}
footer a {{ color: #666; margin: 0 8px; }}
</style>
</head>
<body>
<header>
<h1>Signal</h1>
<p>AI Research for the Curious</p>
</header>

<div class="value-prop">
<p>A weekly newsletter that translates the most important AI research papers into clear, rigorous prose. No hype. No jargon. Every claim grounded in the source.</p>
<ul>
<li>3-5 papers weekly, each ~800-1200 words</li>
<li>Written for engineers, PMs, and founders who use AI but don't read papers</li>
<li>Delivered every Tuesday</li>
</ul>
</div>

<div class="subscribe">
<h2>Subscribe — it's free</h2>
<form action="{subscribe_url}" method="post">
<input type="email" name="email" placeholder="you@example.com" required>
<input type="submit" value="Subscribe">
</form>
</div>

{latest_html}

<footer>
<nav><a href="{config.site_url}/archive.html">Archive</a> <a href="{config.site_url}/rss.xml">RSS</a></nav>
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
    - index.html (edition list)
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

    # Generate index
    index_html = generate_index_page(editions, config)
    (output / "index.html").write_text(index_html)

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
