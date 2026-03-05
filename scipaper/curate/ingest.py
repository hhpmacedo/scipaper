"""
Paper ingestion from multiple sources.
"""

import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Optional
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from .models import Paper, Author, PaperCategory

logger = logging.getLogger(__name__)

# ArXiv Atom feed namespace
ARXIV_NS = "http://www.w3.org/2005/Atom"
ARXIV_API_NS = "http://arxiv.org/schemas/atom"


@dataclass
class IngestConfig:
    """Configuration for ingestion."""
    categories: List[str] = None
    days_back: int = 7
    max_papers: int = 200

    def __post_init__(self):
        if self.categories is None:
            self.categories = [c.value for c in PaperCategory]


class ArxivSource:
    """
    Fetch papers from ArXiv API.

    API Docs: https://info.arxiv.org/help/api/basics.html
    """

    BASE_URL = "http://export.arxiv.org/api/query"
    PAGE_SIZE = 100

    def __init__(self, config: IngestConfig):
        self.config = config

    def _build_query(self) -> str:
        """Build ArXiv search query string for configured categories."""
        cat_queries = [f"cat:{cat}" for cat in self.config.categories]
        return " OR ".join(cat_queries)

    def _parse_entry(self, entry: ET.Element) -> Paper:
        """Parse a single ArXiv Atom entry into a Paper."""
        # Extract ArXiv ID from the entry id URL
        id_url = entry.findtext(f"{{{ARXIV_NS}}}id", "")
        arxiv_id = id_url.split("/abs/")[-1] if "/abs/" in id_url else id_url

        title = entry.findtext(f"{{{ARXIV_NS}}}title", "").strip()
        # Normalize whitespace in title
        title = " ".join(title.split())

        abstract = entry.findtext(f"{{{ARXIV_NS}}}summary", "").strip()
        abstract = " ".join(abstract.split())

        # Authors
        authors = []
        for author_el in entry.findall(f"{{{ARXIV_NS}}}author"):
            name = author_el.findtext(f"{{{ARXIV_NS}}}name", "")
            affiliation_el = author_el.find(f"{{{ARXIV_API_NS}}}affiliation")
            affiliation = affiliation_el.text if affiliation_el is not None else None
            authors.append(Author(name=name, affiliation=affiliation))

        # Categories
        categories = []
        for cat_el in entry.findall(f"{{{ARXIV_NS}}}category"):
            term = cat_el.get("term")
            if term:
                categories.append(term)

        # Published date
        published_str = entry.findtext(f"{{{ARXIV_NS}}}published", "")
        published_date = None
        if published_str:
            try:
                published_date = datetime.fromisoformat(
                    published_str.replace("Z", "+00:00")
                )
            except ValueError:
                pass

        # PDF link
        pdf_url = None
        for link_el in entry.findall(f"{{{ARXIV_NS}}}link"):
            if link_el.get("title") == "pdf":
                pdf_url = link_el.get("href")
                break

        if not pdf_url and arxiv_id:
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

        return Paper(
            arxiv_id=arxiv_id,
            title=title,
            abstract=abstract,
            authors=authors,
            categories=categories,
            published_date=published_date,
            pdf_url=pdf_url,
        )

    async def fetch(self) -> List[Paper]:
        """
        Fetch recent papers from ArXiv.

        Returns list of Paper objects with basic metadata.
        """
        query = self._build_query()
        logger.info(
            f"Fetching papers from ArXiv for categories: {self.config.categories}"
        )

        papers: List[Paper] = []
        start = 0

        async with httpx.AsyncClient(timeout=30.0) as client:
            while len(papers) < self.config.max_papers:
                batch_size = min(
                    self.PAGE_SIZE, self.config.max_papers - len(papers)
                )
                params = {
                    "search_query": query,
                    "start": start,
                    "max_results": batch_size,
                    "sortBy": "submittedDate",
                    "sortOrder": "descending",
                }

                url = f"{self.BASE_URL}?{urlencode(params)}"
                logger.debug(f"Fetching {url}")

                response = await client.get(url)
                response.raise_for_status()

                root = ET.fromstring(response.text)
                entries = root.findall(f"{{{ARXIV_NS}}}entry")

                if not entries:
                    break

                cutoff_date = datetime.utcnow() - timedelta(
                    days=self.config.days_back
                )

                for entry in entries:
                    try:
                        paper = self._parse_entry(entry)
                    except Exception as e:
                        logger.warning(f"Failed to parse entry: {e}")
                        continue

                    # Filter by date
                    if (
                        paper.published_date
                        and paper.published_date.replace(tzinfo=None) < cutoff_date
                    ):
                        # Papers are sorted by date, so we can stop
                        logger.info(
                            f"Reached cutoff date ({cutoff_date.date()}), stopping"
                        )
                        return _deduplicate(papers)

                    papers.append(paper)

                start += len(entries)

                # If we got fewer results than requested, we're done
                if len(entries) < batch_size:
                    break

        papers = _deduplicate(papers)
        logger.info(f"Fetched {len(papers)} papers from ArXiv")
        return papers


class SemanticScholarSource:
    """
    Enrich papers with Semantic Scholar data.

    API Docs: https://api.semanticscholar.org/
    """

    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    async def enrich(self, paper: Paper) -> Paper:
        """
        Add citation counts and other metadata from Semantic Scholar.
        """
        logger.debug(f"Enriching paper {paper.arxiv_id} with Semantic Scholar data")

        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        url = (
            f"{self.BASE_URL}/paper/ArXiv:{paper.arxiv_id}"
            f"?fields=citationCount,referenceCount,externalIds"
        )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)

                if response.status_code == 404:
                    logger.debug(
                        f"Paper {paper.arxiv_id} not found in Semantic Scholar"
                    )
                    return paper

                response.raise_for_status()
                data = response.json()

                paper.citation_count = data.get("citationCount", 0) or 0
                paper.reference_count = data.get("referenceCount", 0) or 0

                ext_ids = data.get("externalIds", {})
                if ext_ids:
                    paper.semantic_scholar_id = ext_ids.get("CorpusId")

        except httpx.HTTPError as e:
            logger.warning(f"Semantic Scholar lookup failed for {paper.arxiv_id}: {e}")

        return paper


class SocialSignalSource:
    """
    Gather social signals (Twitter, HN, Reddit) for papers.
    These are optional enrichments — failures are silently ignored.
    """

    async def get_twitter_mentions(self, paper: Paper) -> int:
        """Count mentions on Twitter/X. Requires API access."""
        # Twitter API requires paid access; return 0 as default
        return 0

    async def get_hn_points(self, paper: Paper) -> int:
        """Check if paper was posted on HN and get points."""
        try:
            url = (
                "https://hn.algolia.com/api/v1/search"
                f"?query={paper.arxiv_id}&tags=story"
            )
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    hits = data.get("hits", [])
                    if hits:
                        return max(h.get("points", 0) or 0 for h in hits)
        except Exception as e:
            logger.debug(f"HN lookup failed for {paper.arxiv_id}: {e}")
        return 0

    async def get_reddit_score(self, paper: Paper) -> int:
        """Check r/MachineLearning for paper mentions."""
        # Reddit API requires OAuth; return 0 as default
        return 0


def _deduplicate(papers: List[Paper]) -> List[Paper]:
    """Deduplicate papers by ArXiv ID."""
    seen = set()
    unique = []
    for paper in papers:
        if paper.arxiv_id not in seen:
            seen.add(paper.arxiv_id)
            unique.append(paper)
    return unique


async def ingest_papers(config: IngestConfig = None) -> List[Paper]:
    """
    Main ingestion pipeline.

    1. Fetch papers from ArXiv
    2. Deduplicate
    3. Enrich with Semantic Scholar data
    4. Add social signals
    5. Return processed papers

    Returns list of ingested papers.
    """
    config = config or IngestConfig()
    logger.info(f"Starting paper ingestion for {config.days_back} days back")

    # Fetch from ArXiv
    arxiv = ArxivSource(config)
    papers = await arxiv.fetch()
    logger.info(f"Fetched {len(papers)} papers from ArXiv")

    # Enrich with Semantic Scholar (best-effort)
    semantic = SemanticScholarSource()
    enriched = []
    for paper in papers:
        try:
            paper = await semantic.enrich(paper)
        except Exception as e:
            logger.warning(f"Failed to enrich {paper.arxiv_id}: {e}")
        enriched.append(paper)

    # Add social signals (optional, don't fail if unavailable)
    social = SocialSignalSource()
    for paper in enriched:
        try:
            paper.hn_points = await social.get_hn_points(paper)
        except Exception as e:
            logger.debug(f"Social signals unavailable for {paper.arxiv_id}: {e}")

    logger.info(f"Ingestion complete: {len(enriched)} papers processed")
    return enriched
