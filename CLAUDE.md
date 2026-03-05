# Signal (scipaper)

Autonomous weekly newsletter pipeline that curates AI research papers and translates them into accessible, citation-grounded prose for technically literate non-researchers.

## Project Status

- **Status**: Ready for First Edition
- **Live URL**: https://signal.hugohmacedo.com
- **Last session**: 2026-03-05
- **Current focus**: Pipeline ready, first run attempted. ArXiv fetch works. Needs API keys in `.env` to complete full run.
- **Next steps**:
  1. Configure `.env` with `ANTHROPIC_API_KEY` and `BUTTONDOWN_API_KEY`
  2. Run first edition: `python -m scipaper --run`
  3. Debug any issues in scoring/generation/verification stages
  4. Commit ArXiv HTTPS fix + dotenv changes
- **Blockers**: None (API keys needed in `.env`)

## Team

This project uses the MetaDeveloper agent team. Agents are defined in `~/Developer/MetaDeveloper/.claude/agents/` and spawned via Task tool.

| Agent  | Role                          | When to engage                                           |
| ------ | ----------------------------- | -------------------------------------------------------- |
| Paula  | PM, AI Strategist, UX         | Mandates, requirements, UX flows, prioritization         |
| Alex   | Architect                     | Pipeline design, API integration patterns, data modeling |
| Diego  | Senior Developer (Full-stack) | Pipeline implementation, LLM integration, async Python   |
| Leo    | Backend Engineer              | API integrations, data stores, scheduling                |
| Teresa | QA                            | Test strategy, verification pipeline validation          |
| Marco  | DevOps                        | GitHub Actions, deployment, monitoring                   |
| Sasha  | Security                      | API key management, dependency audits                    |

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run full pipeline end-to-end
python -m scipaper --run                    # Uses latest anchor document
python -m scipaper --run --week 2025-W10    # Override anchor week
python -m scipaper --run --json-logs        # JSON log output (for CI)

# Run curation stage only
python -m scipaper.curate --fetch           # Fetch papers from ArXiv
python -m scipaper.curate --score           # Score papers
python -m scipaper.curate --select          # Select papers for edition
python -m scipaper.curate --run             # Run full curation pipeline

# Run tests
pytest
pytest tests/test_specific.py::test_name   # Single test

# Lint and format
ruff check .
black .
```

## Architecture

The `scipaper/` package has four subpackages matching the pipeline stages:

```
Ingest --> Curate --> Generate --> Verify --> Publish
```

### `scipaper/curate/` -- Paper discovery and selection

- `models.py` -- Core data models: `Paper`, `Author`, `AnchorDocument`, `ScoredPaper`
- `ingest.py` -- Sources: `ArxivSource`, `SemanticScholarSource`, `SocialSignalSource`
- `score.py` -- Two-axis scoring: `score_relevance()` (embeddings + anchor doc) and `score_narrative_potential()` (LLM-based, uses `NARRATIVE_POTENTIAL_PROMPT`)
- `select.py` -- Greedy selection with diversity constraints (max same institution/topic). Relaxes constraints if minimum count not met.

### `scipaper/generate/` -- Content production

- `pdf_parser.py` -- Fallback chain: PyMuPDF -> GROBID -> LLM extraction. Also handles PDF download from ArXiv.
- `writer.py` -- Citation-grounded generation using `GENERATION_SYSTEM_PROMPT`. Every claim must cite `[section X.Y]`, `[Abstract]`, `[Table N]`, or `[Figure N]`. Includes `extract_citations()` and `validate_citations()` utilities.
- `edition.py` -- Assembles `Edition` from verified `Piece` objects plus `QuickTake` summaries for runners-up.

### `scipaper/verify/` -- Adversarial quality control

- `checker.py` -- Second LLM pass verifies each claim against cited passage. Issues classified by severity (minor/major/critical) and type (unsupported/overstated/misrepresented/missing_context). Rejects on any critical issue or 3+ major issues.
- `style.py` -- Checks against Style Constitution: banned words, required structure (Hook -> Problem -> What They Did -> Results -> Why It Matters), word count (800-1200), citation density. **Fully implemented** (not a stub).

### `scipaper/publish/` -- Delivery

- `email.py` -- HTML + plain text rendering, sending via Buttondown API (creates draft email)
- `web.py` -- Static archive with brutalist design: landing page, edition pages, archive, RSS, JSON feed

## Implementation Status

All modules are fully implemented. Key entry points:

| Module                   | Notes                                                                         |
| ------------------------ | ----------------------------------------------------------------------------- |
| `curate/models.py`       | Core data models: `Paper`, `Author`, `AnchorDocument`, `ScoredPaper`          |
| `curate/ingest.py`       | ArXiv fetch, Semantic Scholar enrichment, HN social signals                   |
| `curate/score.py`        | Relevance scoring (keyword/institution/citation/social) + LLM narrative score |
| `curate/select.py`       | Greedy selection with diversity constraints                                   |
| `generate/pdf_parser.py` | PyMuPDF → GROBID → LLM fallback chain                                         |
| `generate/writer.py`     | LLM generation with citation grounding + validation                           |
| `generate/edition.py`    | Edition assembly with Quick Takes for runners-up                              |
| `verify/checker.py`      | LLM fact-checking with auto-fix, heuristic fallback                           |
| `verify/style.py`        | Rule-based: banned words, structure, citations, word count                    |
| `publish/email.py`       | HTML/text rendering, Buttondown API (creates draft)                           |
| `publish/web.py`         | Brutalist static site: landing, archive, editions, RSS, JSON feed             |
| `pipeline.py`            | End-to-end orchestrator wiring all stages together                            |

## Key Design Decisions

- **Relevance Anchor Document** (`data/anchors/*.yaml`) is the only human input -- a weekly YAML of hot/declining topics, boost keywords, and institutions of interest
- **Citation format:** `[section 3.2]`, `[Abstract]`, `[Table N]`, `[Figure N]` -- inline in generated prose, verified against paper full text
- **Scoring:** Composite of relevance (semantic similarity to anchor + citations + social signals) and narrative potential (LLM-assessed), weighted 50/50
- **Verification rejection:** Any critical issue or >=3 major issues -> paper dropped from edition
- **Style Constitution** (`docs/STYLE_CONSTITUTION.md`) is version-controlled and locked -- all style changes require a logged decision in `docs/DECISIONS.md`

## Key Documentation

- `docs/PRODUCT_SPEC.md` -- Vision, audience, success metrics, piece structure
- `docs/ARCHITECTURE.md` -- Technical design, pipeline diagrams, data stores
- `docs/STYLE_CONSTITUTION.md` -- Writing guidelines (version-controlled, locked)
- `docs/DECISIONS.md` -- Technical decisions log (all resolved: DEC-000 through DEC-005)
- `docs/PHASES.md` -- Development phases (0-6), ~8 weeks to first public edition

## Environment Variables

Required for running the pipeline:

- `ANTHROPIC_API_KEY` -- LLM for scoring, generation, verification (Claude Sonnet)
- `BUTTONDOWN_API_KEY` -- Email delivery (creates draft in Buttondown)
- `SEMANTIC_SCHOLAR_KEY` -- Paper enrichment (optional, graceful fallback)
- `SIGNAL_WEB_URL` -- Web archive base URL (default: `https://signal.hugohmacedo.com`)

## Tech Stack

- **Language:** Python 3.10+ with async throughout (`async def` for all pipeline functions)
- **Key libraries:** `httpx`/`aiohttp` (HTTP), `pymupdf`/`pdfplumber` (PDF), `anthropic`/`openai` (LLM), `sentence-transformers` (embeddings), `pydantic`/`sqlalchemy` (data), `jinja2` (templates), `tenacity` (retries)
- **Data stores:** SQLite for paper DB, local filesystem for PDFs and editions
- **Deployment target:** Vercel (static site), GitHub Actions (pipeline automation)

## Conventions

- All pipeline functions are `async def`
- Prompts are module-level constants (e.g., `GENERATION_SYSTEM_PROMPT`, `NARRATIVE_POTENTIAL_PROMPT`)
- Configuration via `@dataclass` config objects with sensible defaults
- Logging via standard `logging` module
- Tests with `pytest` + `pytest-asyncio`
