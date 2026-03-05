"""
Top-level CLI entrypoint for the Signal pipeline.

Usage:
    python -m scipaper --run              # Run the full pipeline
    python -m scipaper --run --week 2025-W10
    python -m scipaper --run --log-level DEBUG
    python -m scipaper --run --json-logs
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone

from .curate.__main__ import load_anchor
from .pipeline import PipelineConfig, run_pipeline
from .publish.email import ButtondownConfig
from .publish.web import WebConfig


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        })


def setup_logging(log_level: str, json_logs: bool = False) -> None:
    """Configure root logger with optional JSON formatting."""
    handler = logging.StreamHandler()
    if json_logs:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
    logging.root.setLevel(getattr(logging, log_level, logging.INFO))
    logging.root.handlers.clear()
    logging.root.addHandler(handler)


async def cmd_run_pipeline(args) -> None:
    """Run the full pipeline end-to-end."""
    anchor = load_anchor(getattr(args, "week", None))

    config = PipelineConfig(
        email=ButtondownConfig(api_key=os.environ.get("BUTTONDOWN_API_KEY")),
        web=WebConfig(),
        web_base_url=os.environ.get("SIGNAL_WEB_URL", "https://signal.hugohmacedo.com"),
    )

    if getattr(args, "week", None):
        config.week = args.week

    result = await run_pipeline(anchor, config)

    # Summary report
    print("\n=== Signal Pipeline Report ===")
    print(f"  Papers ingested : {result.papers_ingested}")
    print(f"  Papers scored   : {result.papers_scored}")
    print(f"  Papers selected : {result.papers_selected}")
    print(f"  Pieces generated: {result.pieces_generated}")
    print(f"  Pieces verified : {result.pieces_verified}")
    print(f"  Pieces passed   : {result.pieces_passed}")

    if result.errors:
        print(f"\n  Errors ({len(result.errors)}):")
        for err in result.errors:
            print(f"    - {err}")

    if result.edition:
        ed = result.edition
        print(f"\n  Edition: {ed.week} (issue #{ed.issue_number})")
        print(f"  Words  : {ed.total_words}")

    if result.delivery_report:
        dr = result.delivery_report
        print(f"\n  Email delivered: {dr.sent}")

    if result.web_output:
        print(f"  Web output     : {result.web_output}")

    print()

    if result.pieces_passed == 0:
        print("ERROR: No pieces passed verification. Edition not published.")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Signal — autonomous AI research newsletter pipeline",
        prog="python -m scipaper",
    )

    parser.add_argument(
        "--run",
        action="store_true",
        help="Run the full pipeline (ingest → curate → generate → verify → publish)",
    )
    parser.add_argument(
        "--week",
        type=str,
        default=None,
        metavar="WEEK",
        help="Override anchor week (e.g. 2025-W10)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--json-logs",
        action="store_true",
        default=False,
        help="Emit logs as JSON (one object per line)",
    )

    args = parser.parse_args()

    if not args.run:
        parser.print_help()
        return

    setup_logging(args.log_level, json_logs=args.json_logs)

    # Use loop.run_until_complete to avoid asyncio.run()'s signal module
    # interference with our package name. See tests/conftest.py for context.
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(cmd_run_pipeline(args))
    finally:
        loop.close()


if __name__ == "__main__":
    main()
