"""
End-to-end Signal pipeline orchestrator.

Wires together all stages:
  1. Curate:  Ingest → Score → Select
  2. Generate: PDF parse → Write pieces
  3. Verify:  Fact-check → Style check → Auto-fix
  4. Publish: Assemble edition → Email + Web
"""

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .curate.ingest import IngestConfig, ingest_papers
from .curate.models import AnchorDocument, Paper
from .curate.score import ScoringConfig, score_papers
from .curate.select import SelectionConfig, get_runners_up, select_edition_papers
from .generate.edition import AssemblyConfig, Edition, assemble_edition
from .generate.pdf_parser import ParserConfig, download_paper_pdf, parse_paper_pdf
from .generate.writer import GenerationConfig, generate_piece
from .publish.email import ButtondownConfig, DeliveryReport, send_edition_email
from .publish.web import WebConfig, generate_web_archive
from .verify.checker import VerificationConfig, attempt_auto_fix, verify_piece
from .verify.style import StyleConfig, check_style_compliance

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Top-level configuration for the full pipeline."""
    # Stage configs
    ingest: IngestConfig = field(default_factory=IngestConfig)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    selection: SelectionConfig = field(default_factory=SelectionConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    parser: ParserConfig = field(default_factory=ParserConfig)
    verification: VerificationConfig = field(default_factory=VerificationConfig)
    style: StyleConfig = field(default_factory=StyleConfig)
    assembly: AssemblyConfig = field(default_factory=AssemblyConfig)
    email: Optional[ButtondownConfig] = None
    web: Optional[WebConfig] = None

    # Pipeline settings
    week: str = ""
    issue_number: int = 1
    web_base_url: str = "https://signal.hugohmacedo.com"
    pdf_cache_dir: Path = Path("data/pdfs")
    max_verification_retries: int = 1
    skip_pdf_download: bool = False  # For testing without network


@dataclass
class PipelineResult:
    """Result of a full pipeline run."""
    edition: Optional[Edition] = None
    papers_ingested: int = 0
    papers_scored: int = 0
    papers_selected: int = 0
    pieces_generated: int = 0
    pieces_verified: int = 0
    pieces_passed: int = 0
    delivery_report: Optional[DeliveryReport] = None
    web_output: Optional[Path] = None
    errors: List[str] = field(default_factory=list)


async def run_pipeline(
    anchor: AnchorDocument,
    config: Optional[PipelineConfig] = None,
    papers: Optional[List[Paper]] = None,
) -> PipelineResult:
    """
    Run the full Signal pipeline end-to-end.

    Args:
        anchor: Weekly relevance anchor document.
        config: Pipeline configuration.
        papers: Pre-fetched papers (skips ingestion if provided).

    Returns:
        PipelineResult with edition and stats.
    """
    config = config or PipelineConfig()
    result = PipelineResult()

    # ── Stage 1: Curate ──────────────────────────────────────────────
    logger.info("Stage 1: Curating papers")
    stage_start = time.time()

    if papers is None:
        papers = await ingest_papers(config.ingest)
    result.papers_ingested = len(papers)
    logger.info(f"Ingested {len(papers)} papers")

    scored = await score_papers(papers, anchor, config.scoring)
    result.papers_scored = len(scored)
    logger.info(f"Scored {len(scored)} papers")

    selected = select_edition_papers(scored, config.selection)
    runners_up = get_runners_up(scored, selected)
    result.papers_selected = len(selected)
    logger.info(f"Selected {len(selected)} papers, {len(runners_up)} runners-up")
    logger.info(f"Stage 1 complete in {time.time() - stage_start:.1f}s")

    # ── Stage 2: Generate ────────────────────────────────────────────
    logger.info("Stage 2: Generating pieces")
    stage_start = time.time()

    pieces = []
    for sp in selected:
        try:
            paper = sp.paper

            # Download and parse PDF if needed
            if not paper.full_text and not config.skip_pdf_download:
                pdf_path = await download_paper_pdf(
                    paper.arxiv_id, config.pdf_cache_dir
                )
                parsed = await parse_paper_pdf(
                    pdf_path, paper.arxiv_id, config.parser
                )
                paper.full_text = parsed.full_text

            if not paper.full_text:
                logger.warning(f"No full text for {paper.arxiv_id}, skipping")
                continue

            piece = await generate_piece(paper, config.generation)
            pieces.append((piece, paper))
            result.pieces_generated += 1
            logger.info(f"Generated piece for {paper.arxiv_id}")

        except Exception as e:
            msg = f"Generation failed for {sp.paper.arxiv_id}: {e}"
            logger.error(msg)
            result.errors.append(msg)

    logger.info(f"Stage 2 complete in {time.time() - stage_start:.1f}s")

    # ── Stage 3: Verify ──────────────────────────────────────────────
    logger.info("Stage 3: Verifying pieces")
    stage_start = time.time()

    verified_pieces = []
    for piece, paper in pieces:
        try:
            report = await verify_piece(piece, paper, config.verification)
            result.pieces_verified += 1

            # Auto-fix if needed
            if report.status == "needs_revision":
                for attempt in range(config.max_verification_retries):
                    piece = await attempt_auto_fix(
                        piece, report.issues, config.verification
                    )
                    report = await verify_piece(piece, paper, config.verification)
                    if report.status == "pass":
                        break

            # Style check
            style_report = await check_style_compliance(piece, config.style)

            if report.status != "fail" and style_report.compliant:
                piece.verified = True
                piece.verification_report = {
                    "status": report.status,
                    "claims_checked": report.claims_checked,
                    "claims_verified": report.claims_verified,
                    "pass_rate": report.pass_rate,
                }
                verified_pieces.append(piece)
                result.pieces_passed += 1
                logger.info(f"Piece {paper.arxiv_id}: PASSED")
            else:
                reasons = []
                if report.status == "fail":
                    reasons.append(f"verification={report.status}")
                if not style_report.compliant:
                    reasons.append(f"style errors={len([i for i in style_report.issues if i.severity == 'error'])}")
                logger.warning(
                    f"Piece {paper.arxiv_id}: REJECTED ({', '.join(reasons)})"
                )

        except Exception as e:
            msg = f"Verification failed for {piece.paper_id}: {e}"
            logger.error(msg)
            result.errors.append(msg)

    logger.info(f"Stage 3 complete in {time.time() - stage_start:.1f}s")

    # ── Stage 4: Publish ─────────────────────────────────────────────
    logger.info("Stage 4: Publishing edition")
    stage_start = time.time()

    if not verified_pieces:
        logger.warning("No verified pieces — skipping publishing")
        return result

    edition = await assemble_edition(
        verified_pieces,
        runners_up,
        config.week or anchor.week,
        config.issue_number,
        config.assembly,
    )
    result.edition = edition
    logger.info(
        f"Assembled edition: {len(edition.pieces)} pieces, "
        f"{len(edition.quick_takes)} quick takes, "
        f"{edition.total_words} words"
    )

    # Email
    if config.email:
        try:
            report = await send_edition_email(edition, config.email, config.web_base_url)
            result.delivery_report = report
            logger.info(f"Email sent to Buttondown: {report.sent}, id={report.buttondown_id}")
        except Exception as e:
            msg = f"Email delivery failed: {e}"
            logger.error(msg)
            result.errors.append(msg)

    # Web archive
    if config.web:
        try:
            output = await generate_web_archive([edition], config.web)
            result.web_output = output
            logger.info(f"Web archive generated: {output}")
        except Exception as e:
            msg = f"Web generation failed: {e}"
            logger.error(msg)
            result.errors.append(msg)

    logger.info(f"Stage 4 complete in {time.time() - stage_start:.1f}s")
    logger.info(
        f"Pipeline complete: {result.papers_ingested} ingested → "
        f"{result.papers_selected} selected → "
        f"{result.pieces_generated} generated → "
        f"{result.pieces_passed} passed"
    )

    return result
