"""
CLI for the curation pipeline.

Usage:
    python -m scipaper.curate --fetch              # Fetch papers from ArXiv
    python -m scipaper.curate --score              # Score papers
    python -m scipaper.curate --select             # Select papers for edition
    python -m scipaper.curate --run                # Run full pipeline
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .ingest import IngestConfig, ingest_papers
from .models import AnchorDocument, Paper
from .score import ScoringConfig, score_papers
from .select import SelectionConfig, select_edition_papers, get_runners_up

logger = logging.getLogger("scipaper.curate")

DATA_DIR = Path("data")
PAPERS_FILE = DATA_DIR / "papers" / "latest.json"
ANCHORS_DIR = DATA_DIR / "anchors"


def setup_logging(level: str = "INFO"):
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def load_anchor(week: str = None) -> AnchorDocument:
    """Load the most recent anchor document."""
    anchor_files = sorted(ANCHORS_DIR.glob("*.yaml"), reverse=True)

    if week:
        target = ANCHORS_DIR / f"{week}.yaml"
        if target.exists():
            anchor_files = [target]
        else:
            logger.warning(f"Anchor for {week} not found, using latest")

    if not anchor_files:
        logger.error("No anchor documents found in data/anchors/")
        sys.exit(1)

    anchor_path = anchor_files[0]
    logger.info(f"Using anchor: {anchor_path}")

    with open(anchor_path) as f:
        data = yaml.safe_load(f)

    return AnchorDocument(
        week=data.get("week", ""),
        updated_by=data.get("updated_by", ""),
        updated_at=data.get("updated_at", datetime.now(timezone.utc)),
        hot_topics=data.get("hot_topics", []),
        declining_topics=data.get("declining_topics", []),
        boost_keywords=data.get("boost_keywords", []),
        institutions_of_interest=data.get("institutions_of_interest", []),
    )


def save_papers(papers: list, filepath: Path):
    """Save papers to JSON."""
    filepath.parent.mkdir(parents=True, exist_ok=True)

    data = []
    for p in papers:
        paper = p if isinstance(p, Paper) else p.paper
        entry = {
            "arxiv_id": paper.arxiv_id,
            "title": paper.title,
            "abstract": paper.abstract[:500],
            "authors": [{"name": a.name, "affiliation": a.affiliation} for a in paper.authors],
            "categories": paper.categories,
            "published_date": paper.published_date.isoformat() if paper.published_date else None,
            "pdf_url": paper.pdf_url,
            "citation_count": paper.citation_count,
            "hn_points": paper.hn_points,
        }

        # If it's a ScoredPaper, add scores
        if hasattr(p, "relevance_score"):
            entry["relevance_score"] = p.relevance_score
            entry["narrative_potential_score"] = p.narrative_potential_score
            entry["composite_score"] = p.composite_score
            entry["selected_for_edition"] = p.selected_for_edition
            entry["selection_reason"] = p.selection_reason

        data.append(entry)

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, default=str)

    logger.info(f"Saved {len(data)} papers to {filepath}")


def load_papers(filepath: Path) -> list:
    """Load papers from JSON."""
    if not filepath.exists():
        logger.error(f"Papers file not found: {filepath}")
        sys.exit(1)

    with open(filepath) as f:
        data = json.load(f)

    papers = []
    for entry in data:
        from .models import Author
        authors = [
            Author(name=a["name"], affiliation=a.get("affiliation"))
            for a in entry.get("authors", [])
        ]
        published = None
        if entry.get("published_date"):
            try:
                published = datetime.fromisoformat(entry["published_date"])
            except (ValueError, TypeError):
                pass

        papers.append(Paper(
            arxiv_id=entry["arxiv_id"],
            title=entry["title"],
            abstract=entry.get("abstract", ""),
            authors=authors,
            categories=entry.get("categories", []),
            published_date=published,
            pdf_url=entry.get("pdf_url"),
            citation_count=entry.get("citation_count", 0),
            hn_points=entry.get("hn_points", 0),
        ))

    return papers


async def cmd_fetch(args):
    """Fetch papers from ArXiv."""
    config = IngestConfig(
        days_back=args.days_back,
        max_papers=args.max_papers,
    )

    papers = await ingest_papers(config)
    save_papers(papers, PAPERS_FILE)

    print(f"\nFetched {len(papers)} papers")
    for p in papers[:10]:
        print(f"  - [{p.arxiv_id}] {p.title[:80]}")
    if len(papers) > 10:
        print(f"  ... and {len(papers) - 10} more")


async def cmd_score(args):
    """Score papers."""
    papers = load_papers(PAPERS_FILE)
    anchor = load_anchor(args.week)

    scoring_config = ScoringConfig()
    scored = await score_papers(papers, anchor, scoring_config)

    scored_file = DATA_DIR / "papers" / "scored.json"
    save_papers(scored, scored_file)

    print(f"\nScored {len(scored)} papers")
    print("\nTop 10 by composite score:")
    for sp in scored[:10]:
        print(
            f"  {sp.composite_score:.1f} "
            f"(R:{sp.relevance_score:.1f} N:{sp.narrative_potential_score:.1f}) "
            f"[{sp.paper.arxiv_id}] {sp.paper.title[:60]}"
        )


async def cmd_select(args):
    """Select papers for edition."""
    scored_file = DATA_DIR / "papers" / "scored.json"

    if not scored_file.exists():
        print("No scored papers found. Run --score first.")
        sys.exit(1)

    # Load scored papers and re-score them to get ScoredPaper objects
    papers = load_papers(scored_file)
    anchor = load_anchor(args.week)
    scored = await score_papers(papers, anchor)

    selection_config = SelectionConfig(
        target_count=args.target_count,
    )
    selected = select_edition_papers(scored, selection_config)
    runners_up = get_runners_up(scored, selected)

    selected_file = DATA_DIR / "papers" / "selected.json"
    save_papers(selected, selected_file)

    print(f"\nSelected {len(selected)} papers for edition:")
    for sp in selected:
        print(
            f"  [{sp.paper.arxiv_id}] {sp.paper.title[:70]}"
            f" ({sp.selection_reason})"
        )

    print(f"\nRunners-up ({len(runners_up)}):")
    for sp in runners_up[:5]:
        print(
            f"  [{sp.paper.arxiv_id}] {sp.paper.title[:70]}"
            f" (score: {sp.composite_score:.1f})"
        )


async def cmd_run(args):
    """Run full curation pipeline."""
    print("=== Signal Curation Pipeline ===\n")

    # Step 1: Fetch
    print("Step 1: Fetching papers...")
    await cmd_fetch(args)

    # Step 2: Score
    print("\nStep 2: Scoring papers...")
    await cmd_score(args)

    # Step 3: Select
    print("\nStep 3: Selecting papers...")
    await cmd_select(args)

    print("\n=== Pipeline complete ===")


def main():
    parser = argparse.ArgumentParser(
        description="Signal curation pipeline",
        prog="python -m scipaper.curate",
    )

    parser.add_argument(
        "--fetch", action="store_true",
        help="Fetch papers from ArXiv",
    )
    parser.add_argument(
        "--score", action="store_true",
        help="Score papers on relevance and narrative potential",
    )
    parser.add_argument(
        "--select", action="store_true",
        help="Select papers for edition",
    )
    parser.add_argument(
        "--run", action="store_true",
        help="Run full curation pipeline (fetch + score + select)",
    )
    parser.add_argument(
        "--days-back", type=int, default=7,
        help="Number of days to look back (default: 7)",
    )
    parser.add_argument(
        "--max-papers", type=int, default=200,
        help="Maximum papers to fetch (default: 200)",
    )
    parser.add_argument(
        "--target-count", type=int, default=5,
        help="Target number of papers to select (default: 5)",
    )
    parser.add_argument(
        "--week", type=str, default=None,
        help="Anchor document week (e.g., 2025-W10)",
    )
    parser.add_argument(
        "--log-level", type=str, default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()
    setup_logging(args.log_level)

    if args.run:
        asyncio.run(cmd_run(args))
    elif args.fetch:
        asyncio.run(cmd_fetch(args))
    elif args.score:
        asyncio.run(cmd_score(args))
    elif args.select:
        asyncio.run(cmd_select(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
