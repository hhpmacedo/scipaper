"""
Tests for the web archive generation module.
"""

import json

import pytest

from .conftest import run_async

from scipaper.publish.web import (
    WebConfig,
    generate_archive_page,
    generate_edition_page,
    generate_index_page,
    generate_json_feed,
    generate_landing_page,
    generate_rss_feed,
    generate_web_archive,
)
from scipaper.generate.edition import Edition, QuickTake
from scipaper.generate.writer import Piece


def make_piece(paper_id="2403.12345", title="Test Piece", hook="A test hook."):
    return Piece(
        paper_id=paper_id,
        title=title,
        hook=hook,
        content="## The Problem\nProblem text.\n\n## The Results\nResults text.",
        word_count=8,
        citations=[],
        generated_at="2025-01-01",
        model_used="test",
    )


def make_edition(week="2025-W10", issue_number=1, **kwargs):
    defaults = dict(
        week=week,
        issue_number=issue_number,
        pieces=[make_piece()],
        quick_takes=[
            QuickTake(
                paper_id="qt1",
                title="QT Paper",
                one_liner="Brief summary.",
                paper_url="https://arxiv.org/abs/qt1",
            )
        ],
        total_words=100,
    )
    defaults.update(kwargs)
    return Edition(**defaults)


class TestWebConfig:
    def test_default_buttondown_username(self):
        config = WebConfig()
        assert config.buttondown_username == "signal"

    def test_custom_buttondown_username(self):
        config = WebConfig(buttondown_username="hugo")
        assert config.buttondown_username == "hugo"

    def test_default_site_url(self):
        config = WebConfig()
        assert config.site_url == "https://signal.hugohmacedo.com"


class TestGenerateEditionPage:
    def test_valid_html(self):
        edition = make_edition()
        html = generate_edition_page(edition)
        assert "<!DOCTYPE html>" in html
        assert "</html>" in html

    def test_contains_edition_info(self):
        edition = make_edition()
        html = generate_edition_page(edition)
        assert "Signal" in html
        assert "#1" in html
        assert "2025-W10" in html

    def test_contains_pieces(self):
        edition = make_edition()
        html = generate_edition_page(edition)
        assert "Test Piece" in html

    def test_contains_quick_takes(self):
        edition = make_edition()
        html = generate_edition_page(edition)
        assert "Quick Takes" in html
        assert "QT Paper" in html

    def test_includes_rss_link(self):
        edition = make_edition()
        config = WebConfig(site_url="https://signal.test")
        html = generate_edition_page(edition, config)
        assert "rss.xml" in html

    def test_edition_page_has_piece_anchors(self):
        edition = make_edition()
        html = generate_edition_page(edition)
        assert 'id="2403.12345"' in html


class TestGenerateIndexPage:
    def test_valid_html(self):
        editions = [make_edition()]
        html = generate_index_page(editions)
        assert "<!DOCTYPE html>" in html

    def test_lists_editions(self):
        editions = [
            make_edition(week="2025-W10", issue_number=1),
            make_edition(week="2025-W11", issue_number=2),
        ]
        html = generate_index_page(editions)
        assert "2025-W10" in html
        assert "2025-W11" in html
        assert "#1" in html
        assert "#2" in html


class TestGenerateLandingPage:
    def test_valid_html(self):
        editions = [make_edition()]
        html = generate_landing_page(editions)
        assert "<!DOCTYPE html>" in html
        assert "</html>" in html

    def test_contains_branding(self):
        html = generate_landing_page([make_edition()])
        assert "Signal" in html
        assert "AI Research for the Curious" in html

    def test_contains_subscribe_form(self):
        config = WebConfig(buttondown_username="testuser")
        html = generate_landing_page([make_edition()], config)
        assert '<form' in html
        assert 'buttondown.com/api/emails/embed-subscribe/testuser' in html
        assert 'type="email"' in html

    def test_contains_value_prop(self):
        html = generate_landing_page([make_edition()])
        assert "weekly" in html.lower()

    def test_contains_latest_edition_link(self):
        editions = [make_edition(week="2025-W10", issue_number=1)]
        config = WebConfig(site_url="https://signal.test")
        html = generate_landing_page(editions, config)
        assert "2025-W10" in html
        assert "signal.test/editions/2025-W10.html" in html

    def test_contains_archive_link(self):
        config = WebConfig(site_url="https://signal.test")
        html = generate_landing_page([make_edition()], config)
        assert "signal.test/archive.html" in html

    def test_contains_rss_link(self):
        config = WebConfig(site_url="https://signal.test")
        html = generate_landing_page([make_edition()], config)
        assert "rss.xml" in html

    def test_empty_editions(self):
        """Landing page should work with no editions yet."""
        html = generate_landing_page([])
        assert "Signal" in html
        assert '<form' in html


class TestGenerateArchivePage:
    def test_valid_html(self):
        editions = [make_edition()]
        html = generate_archive_page(editions)
        assert "<!DOCTYPE html>" in html

    def test_lists_editions(self):
        editions = [
            make_edition(week="2025-W10", issue_number=1),
            make_edition(week="2025-W11", issue_number=2),
        ]
        html = generate_archive_page(editions)
        assert "2025-W10" in html
        assert "2025-W11" in html

    def test_has_home_link(self):
        """Archive page should link back to the landing page."""
        config = WebConfig(site_url="https://signal.test")
        editions = [make_edition()]
        html = generate_archive_page(editions, config)
        assert 'href="https://signal.test"' in html or 'href="https://signal.test/"' in html


class TestGenerateRssFeed:
    def test_valid_rss(self):
        editions = [make_edition()]
        rss = generate_rss_feed(editions)
        assert '<?xml version="1.0"' in rss
        assert "<rss" in rss
        assert "<channel>" in rss

    def test_contains_items(self):
        editions = [make_edition(week="2025-W10", issue_number=1)]
        rss = generate_rss_feed(editions)
        assert "<item>" in rss
        assert "Signal #1" in rss

    def test_includes_link(self):
        config = WebConfig(site_url="https://signal.test")
        editions = [make_edition()]
        rss = generate_rss_feed(editions, config)
        assert "signal.test" in rss


class TestGenerateJsonFeed:
    def test_valid_json(self):
        editions = [make_edition()]
        feed_str = generate_json_feed(editions)
        feed = json.loads(feed_str)
        assert "version" in feed
        assert "items" in feed

    def test_contains_items(self):
        editions = [make_edition(week="2025-W10", issue_number=1)]
        feed = json.loads(generate_json_feed(editions))
        assert len(feed["items"]) == 1
        assert "Signal #1" in feed["items"][0]["title"]

    def test_jsonfeed_version(self):
        feed = json.loads(generate_json_feed([]))
        assert "jsonfeed.org" in feed["version"]


class TestGenerateWebArchive:
    def test_creates_files(self, tmp_path):
        config = WebConfig(output_dir=tmp_path / "public")
        editions = [make_edition()]

        output = run_async(generate_web_archive(editions, config))

        assert (output / "index.html").exists()
        assert (output / "editions" / "2025-W10.html").exists()
        assert (output / "rss.xml").exists()
        assert (output / "feed.json").exists()

    def test_multiple_editions(self, tmp_path):
        config = WebConfig(output_dir=tmp_path / "public")
        editions = [
            make_edition(week="2025-W10", issue_number=1),
            make_edition(week="2025-W11", issue_number=2),
        ]

        output = run_async(generate_web_archive(editions, config))

        assert (output / "editions" / "2025-W10.html").exists()
        assert (output / "editions" / "2025-W11.html").exists()

        index = (output / "index.html").read_text()
        assert "2025-W10" in index
        assert "2025-W11" in index
