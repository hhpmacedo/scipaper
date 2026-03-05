"""
Tests for the paper ingestion module.
"""

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from .conftest import run_async

from signal.curate.ingest import (
    ArxivSource,
    IngestConfig,
    SemanticScholarSource,
    SocialSignalSource,
    _deduplicate,
)
from signal.curate.models import Author, Paper


def make_paper(arxiv_id="2403.12345", title="Test Paper", **kwargs):
    defaults = dict(
        arxiv_id=arxiv_id,
        title=title,
        abstract="This paper presents a method for testing.",
        authors=[Author(name="Test Author", affiliation="Test University")],
        categories=["cs.AI"],
        published_date=datetime.utcnow() - timedelta(days=2),
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}.pdf",
    )
    defaults.update(kwargs)
    return Paper(**defaults)


SAMPLE_ARXIV_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <title>ArXiv Query</title>
  <entry>
    <id>http://arxiv.org/abs/2403.12345v1</id>
    <title>Test Paper: A Novel Approach to Testing</title>
    <summary>This paper presents a novel approach to automated testing of AI systems.</summary>
    <published>{published}</published>
    <author><name>Alice Smith</name></author>
    <author>
      <name>Bob Jones</name>
      <arxiv:affiliation>MIT</arxiv:affiliation>
    </author>
    <category term="cs.AI" />
    <category term="cs.LG" />
    <link title="pdf" href="https://arxiv.org/pdf/2403.12345v1" />
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2403.12346v1</id>
    <title>Another Paper</title>
    <summary>Another test abstract.</summary>
    <published>{published}</published>
    <author><name>Carol White</name></author>
    <category term="cs.CL" />
  </entry>
</feed>
"""


class TestArxivSource:
    def test_build_query(self):
        config = IngestConfig(categories=["cs.AI", "cs.LG"])
        source = ArxivSource(config)
        query = source._build_query()
        assert "cat:cs.AI" in query
        assert "cat:cs.LG" in query
        assert " OR " in query

    def test_parse_entry(self):
        published = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        xml_text = SAMPLE_ARXIV_RESPONSE.format(published=published)
        root = ET.fromstring(xml_text)
        ns = "http://www.w3.org/2005/Atom"
        entries = root.findall(f"{{{ns}}}entry")

        config = IngestConfig()
        source = ArxivSource(config)

        paper = source._parse_entry(entries[0])
        assert paper.arxiv_id == "2403.12345v1"
        assert "Novel Approach" in paper.title
        assert len(paper.authors) == 2
        assert paper.authors[1].affiliation == "MIT"
        assert "cs.AI" in paper.categories
        assert "cs.LG" in paper.categories
        assert paper.pdf_url is not None

    def test_fetch_parses_response(self):
        published = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        xml_text = SAMPLE_ARXIV_RESPONSE.format(published=published)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = xml_text
        mock_response.raise_for_status = MagicMock()

        config = IngestConfig(max_papers=10)
        source = ArxivSource(config)

        with patch("signal.curate.ingest.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client

            papers = run_async(source.fetch())

        assert len(papers) == 2
        assert papers[0].arxiv_id == "2403.12345v1"
        assert papers[1].arxiv_id == "2403.12346v1"


class TestSemanticScholarSource:
    def test_enrich_success(self):
        paper = make_paper()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "citationCount": 42,
            "referenceCount": 15,
            "externalIds": {"CorpusId": "12345"},
        }
        mock_response.raise_for_status = MagicMock()

        with patch("signal.curate.ingest.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client

            source = SemanticScholarSource()
            enriched = run_async(source.enrich(paper))

        assert enriched.citation_count == 42
        assert enriched.reference_count == 15

    def test_enrich_not_found(self):
        paper = make_paper()
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("signal.curate.ingest.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client

            source = SemanticScholarSource()
            result = run_async(source.enrich(paper))

        assert result.citation_count == 0


class TestDeduplication:
    def test_removes_duplicates(self):
        papers = [
            make_paper(arxiv_id="1"),
            make_paper(arxiv_id="2"),
            make_paper(arxiv_id="1"),
            make_paper(arxiv_id="3"),
            make_paper(arxiv_id="2"),
        ]
        result = _deduplicate(papers)
        assert len(result) == 3
        assert [p.arxiv_id for p in result] == ["1", "2", "3"]

    def test_empty_list(self):
        assert _deduplicate([]) == []

    def test_no_duplicates(self):
        papers = [make_paper(arxiv_id=str(i)) for i in range(5)]
        assert len(_deduplicate(papers)) == 5


class TestSocialSignals:
    def test_twitter_returns_zero(self):
        source = SocialSignalSource()
        paper = make_paper()
        assert run_async(source.get_twitter_mentions(paper)) == 0

    def test_reddit_returns_zero(self):
        source = SocialSignalSource()
        paper = make_paper()
        assert run_async(source.get_reddit_score(paper)) == 0
