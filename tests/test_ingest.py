"""
Tests for the paper ingestion module.
"""

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch


from .conftest import run_async

from scipaper.curate.ingest import (
    ArxivSource,
    IngestConfig,
    SemanticScholarSource,
    SocialSignalSource,
    _deduplicate,
)
from scipaper.curate.models import Author, Paper


def make_paper(arxiv_id="2403.12345", title="Test Paper", **kwargs):
    defaults = dict(
        arxiv_id=arxiv_id,
        title=title,
        abstract="This paper presents a method for testing.",
        authors=[Author(name="Test Author", affiliation="Test University")],
        categories=["cs.AI"],
        published_date=datetime.now(timezone.utc) - timedelta(days=2),
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
        published = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
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
        published = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        xml_text = SAMPLE_ARXIV_RESPONSE.format(published=published)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = xml_text
        mock_response.raise_for_status = MagicMock()

        config = IngestConfig(max_papers=10)
        source = ArxivSource(config)

        with patch("scipaper.curate.ingest.httpx.AsyncClient") as MockClient:
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

        with patch("scipaper.curate.ingest.httpx.AsyncClient") as MockClient:
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

        with patch("scipaper.curate.ingest.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client

            source = SemanticScholarSource()
            result = run_async(source.enrich(paper))

        assert result.citation_count == 0


def test_semantic_scholar_pulls_influential_and_hindex():
    from scipaper.curate.ingest import SemanticScholarSource
    from scipaper.curate.models import Paper
    from .conftest import run_async

    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"citationCount": 40, "referenceCount": 30,
                    "influentialCitationCount": 7,
                    "externalIds": {"CorpusId": 123},
                    "authors": [{"hIndex": 55}, {"hIndex": 12}]}
    class FakeClient:
        async def get(self, *a, **k): return FakeResp()

    paper = Paper(arxiv_id="2607.00001", title="t", abstract="a")
    out = run_async(SemanticScholarSource().enrich(paper, FakeClient()))
    assert out.citation_count == 40
    assert out.influential_citation_count == 7
    assert out.max_author_h_index == 55


def test_semantic_scholar_degrades_on_error():
    from scipaper.curate.ingest import SemanticScholarSource
    from scipaper.curate.models import Paper
    from .conftest import run_async

    class BoomClient:
        async def get(self, *a, **k): raise RuntimeError("down")

    paper = Paper(arxiv_id="2607.00002", title="t", abstract="a")
    out = run_async(SemanticScholarSource().enrich(paper, BoomClient()))
    assert out.influential_citation_count == 0 and out.max_author_h_index == 0


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

    def test_reddit_score_returns_max_score(self):
        from scipaper.curate.ingest import SocialSignalSource
        from scipaper.curate.models import Paper
        from .conftest import run_async

        class FakeResp:
            status_code = 200

            def json(self):
                return {"data": {"children": [
                    {"data": {"score": 12}}, {"data": {"score": 47}}, {"data": {"score": 3}}]}}

        class FakeClient:
            async def get(self, *a, **k):
                return FakeResp()

        score = run_async(SocialSignalSource().get_reddit_score(Paper(arxiv_id="2607.1", title="t", abstract="a"), FakeClient()))
        assert score == 47

    def test_reddit_score_degrades_to_zero_on_error(self):
        from scipaper.curate.ingest import SocialSignalSource
        from scipaper.curate.models import Paper
        from .conftest import run_async

        class BoomClient:
            async def get(self, *a, **k):
                raise RuntimeError("down")

        score = run_async(SocialSignalSource().get_reddit_score(Paper(arxiv_id="2607.2", title="t", abstract="a"), BoomClient()))
        assert score == 0

    def test_reddit_score_degrades_on_bad_shape(self):
        from scipaper.curate.ingest import SocialSignalSource
        from scipaper.curate.models import Paper
        from .conftest import run_async

        class WeirdResp:
            status_code = 200

            def json(self):
                return {"unexpected": True}

        class WeirdClient:
            async def get(self, *a, **k):
                return WeirdResp()

        score = run_async(SocialSignalSource().get_reddit_score(Paper(arxiv_id="2607.3", title="t", abstract="a"), WeirdClient()))
        assert score == 0


def test_hf_upvotes_parsed():
    from scipaper.curate.ingest import CommunitySignalSource
    from scipaper.curate.models import Paper
    from .conftest import run_async
    class Resp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"upvotes": 120, "title": "x"}
    class Client:
        async def get(self, *a, **k): return Resp()
    v = run_async(CommunitySignalSource().get_hf_upvotes(Paper(arxiv_id="2607.1", title="t", abstract="a"), Client()))
    assert v == 120


def test_hf_upvotes_degrades():
    from scipaper.curate.ingest import CommunitySignalSource
    from scipaper.curate.models import Paper
    from .conftest import run_async
    class Boom:
        async def get(self, *a, **k): raise RuntimeError("x")
    assert run_async(CommunitySignalSource().get_hf_upvotes(Paper(arxiv_id="a", title="t", abstract="a"), Boom())) == 0
    class Weird:
        async def get(self, *a, **k):
            class R:
                status_code = 200
                def raise_for_status(self): pass
                def json(self): return {"nope": 1}
            return R()
    assert run_async(CommunitySignalSource().get_hf_upvotes(Paper(arxiv_id="a", title="t", abstract="a"), Weird())) == 0


def test_github_stars_none_repo_no_call():
    from scipaper.curate.ingest import CommunitySignalSource
    from scipaper.curate.models import Paper
    from .conftest import run_async
    class Client:
        async def get(self, *a, **k): raise AssertionError("should not be called when github_repo is None")
    assert run_async(CommunitySignalSource().get_github_stars(Paper(arxiv_id="a", title="t", abstract="a"), Client())) == 0


def test_github_stars_parsed():
    from scipaper.curate.ingest import CommunitySignalSource
    from scipaper.curate.models import Paper
    from .conftest import run_async
    class Resp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"stargazers_count": 850}
    class Client:
        async def get(self, *a, **k): return Resp()
    p = Paper(arxiv_id="a", title="t", abstract="a", github_repo="foo/bar")
    assert run_async(CommunitySignalSource().get_github_stars(p, Client())) == 850


def test_ingest_config_covers_broadened_fields():
    from scipaper.curate.ingest import IngestConfig
    cfg = IngestConfig()
    cats = set(cfg.categories)
    assert {"cs.AI", "cs.LG", "cs.CL", "stat.ML"} <= cats
    for c in ["cs.CV", "cs.RO", "cs.MA", "cs.HC", "cs.CY", "cs.SE", "cs.CR", "eess.AS"]:
        assert c in cats, f"missing broadened category {c}"


def test_build_query_includes_broadened_categories():
    from scipaper.curate.ingest import IngestConfig, ArxivSource
    q = ArxivSource(IngestConfig())._build_query()
    assert "cat:cs.RO" in q and "cat:cs.CV" in q and "cat:cs.CL" in q


def test_twitter_disabled_makes_no_call_and_returns_zero():
    from scipaper.curate.ingest import SocialSignalSource
    from scipaper.curate.models import Paper
    from .conftest import run_async

    class Boom:
        async def get(self, *a, **k): raise AssertionError("must not call when disabled")

    src = SocialSignalSource()
    # disabled by default (no flag, no token)
    assert run_async(src.get_twitter_mentions(Paper(arxiv_id="a", title="t", abstract="x"), client=Boom())) == 0


def test_twitter_enabled_parses_count():
    from scipaper.curate.ingest import SocialSignalSource
    from scipaper.curate.models import Paper
    from .conftest import run_async

    class Resp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"meta": {"total_tweet_count": 37}}
    class Client:
        async def get(self, *a, **k): return Resp()

    src = SocialSignalSource()
    n = run_async(src.get_twitter_mentions(
        Paper(arxiv_id="a", title="t", abstract="x"),
        client=Client(), enabled=True, bearer_token="tok"))
    assert n == 37


def test_twitter_enabled_degrades_on_error():
    from scipaper.curate.ingest import SocialSignalSource
    from scipaper.curate.models import Paper
    from .conftest import run_async

    class Boom:
        async def get(self, *a, **k): raise RuntimeError("down")

    src = SocialSignalSource()
    assert run_async(src.get_twitter_mentions(
        Paper(arxiv_id="a", title="t", abstract="x"),
        client=Boom(), enabled=True, bearer_token="tok")) == 0
