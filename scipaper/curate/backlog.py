"""
Persistent paper backlog.

Signal runs weekly and only ever looks at the current week's fresh papers by
default. This module lets papers survive across runs so they can be
reconsidered for up to ~28 days (the "rolling coverage window") as their
traction signals (citations, HN points, GitHub stars, etc.) accrue.

Degradable by design: a missing or corrupt backlog file yields an empty
backlog rather than raising. The backlog is just a cache of candidates —
losing it should never take down the pipeline.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from scipaper.curate.models import Author, Paper

logger = logging.getLogger(__name__)

# Fields captured in the backlog. Deliberately excludes full_text (large,
# fetched later at generation time) and other transient/derived fields.
_PAPER_FIELDS = [
    "arxiv_id",
    "title",
    "abstract",
    "categories",
    "pdf_url",
    "semantic_scholar_id",
    "citation_count",
    "reference_count",
    "influential_citation_count",
    "max_author_h_index",
    "twitter_mentions",
    "hn_points",
    "reddit_score",
    "hf_upvotes",
    "github_stars",
    "github_repo",
]


def _paper_to_dict(paper: Paper) -> dict:
    """Serialize the persisted subset of a Paper's fields to a JSON-safe dict."""
    d = {field: getattr(paper, field) for field in _PAPER_FIELDS}
    d["published_date"] = (
        paper.published_date.isoformat() if paper.published_date else None
    )
    d["authors"] = [
        {"name": a.name, "affiliation": a.affiliation} for a in (paper.authors or [])
    ]
    return d


def _dict_to_paper(d: dict) -> Paper:
    """Reconstruct a Paper from the dict produced by _paper_to_dict."""
    kwargs = {field: d.get(field) for field in _PAPER_FIELDS if field in d}
    # Restore defaults for fields that require non-None values.
    kwargs.setdefault("categories", [])
    if kwargs.get("categories") is None:
        kwargs["categories"] = []

    published_date = d.get("published_date")
    kwargs["published_date"] = (
        datetime.fromisoformat(published_date) if published_date else None
    )

    kwargs["authors"] = [
        Author(name=a.get("name"), affiliation=a.get("affiliation"))
        for a in (d.get("authors") or [])
    ]

    return Paper(**kwargs)


def _to_naive(dt: datetime) -> datetime:
    """Strip tzinfo so age comparisons are safe regardless of input tz-awareness."""
    return dt.replace(tzinfo=None)


class Backlog:
    """
    A persistent, JSON-backed store of candidate papers, keyed by arxiv_id.

    Missing or corrupt backing files degrade to an empty backlog rather than
    raising -- this store is a cache of candidates, not a source of truth.
    """

    def __init__(self, path):
        self.path = Path(path)
        self._data: dict = self._load()

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            raw = self.path.read_text()
            data = json.loads(raw)
            if not isinstance(data, dict):
                logger.warning(
                    "Backlog file %s did not contain a JSON object; starting empty",
                    self.path,
                )
                return {}
            return data
        except Exception:
            logger.warning(
                "Failed to load backlog file %s; starting empty", self.path,
                exc_info=True,
            )
            return {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(self._data, indent=2))
        tmp_path.replace(self.path)

    def merge_new(self, papers: List[Paper], seen_at: datetime) -> None:
        """
        Merge freshly-ingested papers into the backlog.

        New arxiv_ids are recorded with first_seen == last_seen == seen_at.
        Existing arxiv_ids get their stored paper subset replaced with the
        newer version (so refreshed signals win) and last_seen bumped,
        while first_seen/covered/covered_week are preserved.
        """
        seen_at_iso = seen_at.isoformat()
        for paper in papers:
            existing = self._data.get(paper.arxiv_id)
            if existing is None:
                self._data[paper.arxiv_id] = {
                    "paper": _paper_to_dict(paper),
                    "first_seen": seen_at_iso,
                    "last_seen": seen_at_iso,
                    "covered": False,
                    "covered_week": None,
                }
            else:
                existing["paper"] = _paper_to_dict(paper)
                existing["last_seen"] = seen_at_iso
        self.save()

    def eligible(
        self,
        now: Optional[datetime] = None,
        within_days: int = 28,
        exclude_covered: bool = True,
    ) -> List[Paper]:
        """
        Return papers still within the rolling coverage window.

        Age is measured from published_date when available, otherwise from
        first_seen. Papers marked covered are excluded unless
        exclude_covered=False.
        """
        if now is None:
            now = datetime.now(timezone.utc)
        now_naive = _to_naive(now)

        results = []
        for arxiv_id, record in self._data.items():
            if exclude_covered and record.get("covered"):
                continue
            paper = _dict_to_paper(record["paper"])
            if paper.published_date is not None:
                reference = paper.published_date
            else:
                reference = datetime.fromisoformat(record["first_seen"])
            age_days = (now_naive - _to_naive(reference)).days
            if age_days <= within_days:
                results.append(paper)
        return results

    def mark_covered(self, ids: List[str], week: str) -> None:
        """Mark the given arxiv_ids as covered in the given edition week, then persist."""
        for arxiv_id in ids:
            record = self._data.get(arxiv_id)
            if record is not None:
                record["covered"] = True
                record["covered_week"] = week
        self.save()
