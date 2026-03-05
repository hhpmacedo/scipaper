"""
Tests for the web archive generation module.
"""

import json

import pytest

from .conftest import run_async

from signal.publish.web import (
    WebConfig,
    generate_edition_page,
    generate_index_page,
    generate_json_feed,
    generate_rss_feed,
    generate_web_archive,
)
from signal.generate.edition import Edition, QuickTake
from signal.generate.writer import Piece


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
