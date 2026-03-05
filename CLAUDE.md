# Signal (scipaper)

Autonomous weekly newsletter pipeline that curates AI research papers and translates them into accessible, citation-grounded prose for technically literate non-researchers.

## Project Status

- **Status**: Active Development
- **Live URL**: https://signal.hugohmacedo.com
- **Last session**: 2026-03-05
- **Current focus**: Site deployed to Vercel. Landing page live with Buttondown subscribe form. 205 tests pass, lint clean.
- **Next steps**:
  1. Configure Buttondown account (create, set username, paste welcome email from `docs/welcome-email.md`)
  2. Run first real edition end-to-end with live API keys
- **Blockers**: None

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

# Run pipeline stages (once implemented)
python -m signal.curate      # Fetch, score, and select papers
python -m signal.generate    # Generate citation-grounded pieces
python -m signal.publish     # Publish via email and web

# Run tests
pytest
pytest tests/test_specific.py::test_name   # Single test

# Lint and format
ruff check .
black .
```

## Architecture

The `signal/` package has four subpackages matching the pipeline stages:

```
Ingest --> Curate --> Generate --> Verify --> Publish
```

### `signal/curate/` -- Paper discovery and selection

- `models.py` -- Core data models: `Paper`, `Author`, `AnchorDocument`, `ScoredPaper`
- `ingest.py` -- Sources: `ArxivSource`, `SemanticScholarSource`, `SocialSignalSource`
- `score.py` -- Two-axis scoring: `score_relevance()` (embeddings + anchor doc) and `score_narrative_potential()` (LLM-based, uses `NARRATIVE_POTENTIAL_PROMPT`)
- `select.py` -- Greedy selection with diversity constraints (max same institution/topic). Relaxes constraints if minimum count not met.

### `signal/generate/` -- Content production

- `pdf_parser.py` -- Fallback chain: PyMuPDF -> GROBID -> LLM extraction. Also handles PDF download from ArXiv.
- `writer.py` -- Citation-grounded generation using `GENERATION_SYSTEM_PROMPT`. Every claim must cite `[section X.Y]`, `[Abstract]`, `[Table N]`, or `[Figure N]`. Includes `extract_citations()` and `validate_citations()` utilities.
- `edition.py` -- Assembles `Edition` from verified `Piece` objects plus `QuickTake` summaries for runners-up.

### `signal/verify/` -- Adversarial quality control

- `checker.py` -- Second LLM pass verifies each claim against cited passage. Issues classified by severity (minor/major/critical) and type (unsupported/overstated/misrepresented/missing_context). Rejects on any critical issue or 3+ major issues.
- `style.py` -- Checks against Style Constitution: banned words, required structure (Hook -> Problem -> What They Did -> Results -> Why It Matters), word count (800-1200), citation density. **Fully implemented** (not a stub).

### `signal/publish/` -- Delivery

- `email.py` -- HTML + plain text rendering via Jinja2, sending via Resend/Postmark/SendGrid
- `web.py` -- Static archive: edition pages, index, RSS, JSON feed

## Implementation Status

| Module                   | Status | Notes                                                                         |
| ------------------------ | ------ | ----------------------------------------------------------------------------- |
| `curate/models.py`       | Done   | All data models complete                                                      |
| `curate/ingest.py`       | Stub   | ArXiv, Semantic Scholar, Social -- all `NotImplementedError`                  |
| `curate/score.py`        | Stub   | Prompts written, scoring logic stubbed                                        |
| `curate/select.py`       | Done   | Selection + diversity logic implemented                                       |
| `generate/pdf_parser.py` | Stub   | Download works, all parsers stubbed                                           |
| `generate/writer.py`     | Stub   | Prompts written, `extract_citations()` and `validate_citations()` implemented |
| `generate/edition.py`    | Stub   | Assembly logic written, Quick Take generation stubbed                         |
| `verify/checker.py`      | Stub   | Prompts written, rejection logic implemented, verification stubbed            |
| `verify/style.py`        | Done   | Fully implemented -- banned words, structure, citations, word count           |
| `publish/email.py`       | Stub   | All rendering and sending stubbed                                             |
| `publish/web.py`         | Stub   | All generation stubbed                                                        |

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
- `docs/DECISIONS.md` -- Technical decisions log (4 open: LLM model, PDF parsing, email provider, failure handling)
- `docs/PHASES.md` -- Development phases (0-6), ~8 weeks to first public edition

## Environment Variables

Required API keys (see `.env.example`):

- `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` -- LLM for scoring, generation, verification
- `SEMANTIC_SCHOLAR_KEY` -- Paper enrichment
- Email provider key (Resend/Postmark/SendGrid)

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
