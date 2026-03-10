# Signal (scipaper) - Session Log

Append-only session log. Each entry captures what happened and where to pick up.

---

## 2026-03-05 - Project onboarding to MetaDeveloper team

**What happened:**

- Paula explored the full codebase to understand project state
- Created proper CLAUDE.md with Project Status section following MetaDeveloper conventions
- Added Team section referencing MetaDeveloper agents for Task tool spawning
- Added Implementation Status table showing what is Done vs Stub
- Created this `docs/sessions.md` for session continuity
- Added scipaper to MetaDeveloper portfolio table

**Project state discovered:**

- Product name: Signal -- AI Research for the Curious
- Python async pipeline: Ingest -> Curate -> Generate -> Verify -> Publish
- Well-documented: product spec, architecture, style constitution, phases, decisions log
- Code scaffolded with data models, prompts, and pipeline structure
- 3 modules fully implemented: `curate/models.py`, `curate/select.py`, `verify/style.py`
- Everything else raises `NotImplementedError` -- ready for Phase 0
- 4 open technical decisions need resolution before implementation
- No tests, templates, or scripts directories created yet

**Next session:**

- Resolve DEC-001 (LLM model selection) and DEC-002 (PDF parsing strategy)
- Begin Phase 0: ArXiv API integration, basic PDF parsing
- Set up Python venv and verify all dependencies install cleanly

---

### 2026-03-05 16:49 — Phase 5 + Phase 6 Complete

**What was done:**

- Finished Phase 5 (Automation & Monitoring): lint fixes, pushed 9 commits
- Designed Phase 6 (Polish & Launch): brainstormed approach, wrote design doc + impl plan
- Implemented Phase 6 via subagent-driven development (9 tasks, 10 commits):
  - `generate_landing_page()` with Buttondown subscribe form embed
  - Renamed `generate_index_page` → `generate_archive_page` (index.html = landing, archive.html = edition list)
  - Updated all nav links (edition pages, archive, landing)
  - Updated all URL defaults to `signal.hugohmacedo.com`
  - Drafted welcome email copy (`docs/welcome-email.md`)
- Cleaned up 17 pre-existing unused imports across test suite
- All pushed to origin/main

**Key decisions:**

- Buttondown handles subscribers, analytics, welcome email delivery — minimal custom code
- Static landing page generated alongside web archive (not a separate platform)
- Domain: `signal.hugohmacedo.com`, recommended hosting: GitHub Pages

**State:** 205 tests passing, lint clean, Phases 0-6 complete. Code ready for production. Needs manual infra setup.

**Next steps:**

1. Set up hosting (GitHub Pages recommended) for `signal.hugohmacedo.com`
2. Configure Buttondown account + paste welcome email from `docs/welcome-email.md`
3. Set up DNS CNAME: `signal.hugohmacedo.com` → hosting provider
4. Run first real edition end-to-end with live API keys

---

### 2026-03-05 17:08 — Vercel Deployment Live

**What was done:**

- Designed deployment approach: Vercel static site serving `public/` directory
- Created `vercel.json` with output directory, clean URL rewrites (`/archive`, `/rss`), content-type headers for feeds
- Generated placeholder `public/index.html` (landing page) and `public/archive.html` (empty archive) using existing `generate_landing_page()` / `generate_archive_page()`
- Wrote design doc: `docs/plans/2026-03-05-vercel-deployment-design.md`
- Committed, pushed, and verified site is live at `signal.hugohmacedo.com`

**Key decisions:**

- Vercel over GitHub Pages — Hugo's domain already on Vercel, keeps hosting in one place
- Manual-first workflow: generate locally → commit `public/` → push → Vercel auto-deploys
- `public/` committed to repo (not gitignored) since Vercel deploys from repo contents
- Updated CLAUDE.md deployment target from "Railway/Fly.io" to "Vercel"

**State:** Site live at signal.hugohmacedo.com. Landing page with subscribe form working. Archive empty (no editions yet). 205 tests passing.

**Next steps:**

1. Configure Buttondown account (create, set username, paste welcome email from `docs/welcome-email.md`)
2. Run first real edition end-to-end with live API keys
3. Later: add CI-driven deployment via GitHub Actions + Vercel CLI

---

### 2026-03-05 17:52 — Deployment, Buttondown, Brutalist Redesign

**What was done:**

- Set up Vercel deployment: `vercel.json`, placeholder `public/` pages, design doc
- Verified site live at signal.hugohmacedo.com
- Updated Buttondown username to `signalhhmacedo` (code, tests, generated pages)
- Redesigned all pages with bold brutalist style (Helvetica Neue chrome, thick black rules, red-orange `#e63b19` accent)
- Added `/subscribed.html` confirmation page with JS form submission (stays on-domain)
- Redesigned archive and edition templates to match brutalist system
- Guided Buttondown account setup (name, welcome email)

**Key decisions:**

- Vercel hosting (Hugo's domain already there), manual-first deploy workflow
- Bold/typographic brutalist: Helvetica Neue for chrome, Georgia serif for edition body readability
- JS form submit to Buttondown API with `mode: 'no-cors'`, redirect to own confirmation page
- Edition pages use smaller 48px SIGNAL header; landing uses 80px

**State:** Site live at signal.hugohmacedo.com. All pages (landing, subscribed, archive, edition) share brutalist design. Buttondown configured. Subscribe flow works end-to-end. 205 tests passing. Pipeline modules still stubbed.

**Next steps:**

1. Implement pipeline stubs for first real edition (ingest → score → parse → write → verify → publish)
2. Create sample anchor document (`data/anchors/`)
3. Set up `.env` with API keys (Anthropic, Semantic Scholar, Buttondown)

---

### 2026-03-05 18:23 — Pipeline Verification & First Run Attempt

**What was done:**

- Explored full codebase: discovered all pipeline modules are fully implemented (zero `NotImplementedError` stubs)
- Updated CLAUDE.md — corrected outdated "Stub" labels, fixed package name (`signal/` → `scipaper/`), updated commands, env vars, decisions
- Cleaned up stale branches: deleted local `review/signal-pipeline` + remote `claude/signal-curation-pipeline-kax8x`
- Added dotenv support (`load_dotenv()` in `__main__.py` + `.env.example`)
- Fixed ArXiv API URL: `http://` → `https://` (was returning 301 Moved Permanently)
- First pipeline run attempted — ArXiv fetch now works

**Key decisions:**

- Dotenv for local API key management (`.env` in `.gitignore`, `.env.example` committed)
- Semantic Scholar key confirmed optional (graceful fallback, not required)

**State:** Pipeline runs through ArXiv fetch. Needs `ANTHROPIC_API_KEY` and `BUTTONDOWN_API_KEY` in `.env` to complete full run. 205 tests passing. ArXiv HTTPS fix uncommitted.

**Next steps:**

1. Configure `.env` with API keys and re-run `python -m scipaper --run`
2. Debug any issues in scoring/generation/verification stages
3. Commit and push ArXiv HTTPS fix

---

### 2026-03-05 19:50 — API Optimization + First Edition Published

**What was done:**

- Full API optimization (10 tasks via subagent-driven development):
  - Smart text truncation (`text_utils.py`) — strips references/appendix before LLM input
  - Expanded retry logic (`retry.py`) — handles 429, 503, Anthropic rate limits
  - Shared `ClientPool` (`clients.py`) — async context manager for httpx/anthropic/openai
  - SQLite cache (`cache.py`) — keyed by `(arxiv_id, stage, model_version)`
  - Fixed model version drift — single source of truth in `config/__init__.py`
  - Dropped LLM quick takes — heuristic-only for runners-up
  - Concurrent enrichment in ingest — `asyncio.gather` with semaphores
  - Two-pass scoring — pure Python relevance filter, LLM narrative for top 20 only
  - Wired optimizations into pipeline with `--no-cache` CLI flag
- Changed default generation model to Opus 4.6 (Sonnet stays for scoring/verification)
- Production readiness audit — all modules implemented, 228 tests, zero stubs
- Added Vercel deploy step to `weekly-edition.yml` (via Vercel CLI `--prod`)
- Published first edition (2026-W10): 3 pieces, 2845 words, pushed to live site

**Key decisions:**

- Two-pass scoring cuts LLM calls from ~230 to ~35 per run
- Opus 4.6 for article generation (quality), Sonnet for scoring/verification (speed/cost)
- Vercel CLI deploy from GitHub Actions (not git-commit-and-push pattern)
- ClientPool and PipelineCache created+tested but not yet injected into module functions (deferred)

**State:** Edition #1 live at signal.hugohmacedo.com. 228 tests passing. Automated weekly workflow ready (needs Vercel secrets: `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`).

**Next steps:**

1. Verify Vercel secrets are set and test a manual workflow dispatch
2. Create anchor document for next week (automate weekly template)
3. Wire `ClientPool` and `PipelineCache` into individual module functions
4. Set up failure alerting (Slack/email on pipeline failure)

---

### 2026-03-05 19:51 — Paper metadata + About page

**What was done:**

- Added `paper_url` and `authors` fields to `Piece` dataclass in `writer.py`
- Updated `generate_piece()` to populate paper URL and author names from `Paper` object
- Updated edition HTML template in `web.py`: titles now link to papers, author bylines displayed
- Created `generate_about_page()` in `web.py` — "How It Works" page with 4 sections explaining pipeline
- Added About link to all footer navs (edition, landing, subscribed, archive, about pages)
- Generated static `public/about.html`, updated `public/index.html` and `public/archive.html` footers
- Committed and pushed all changes

**Key decisions:**

- About page focuses on service/methodology, not personal — builds trust by showing the pipeline
- Paper titles link to `pdf_url` with fallback to `arxiv.org/abs/{id}`

**State:** All changes committed and pushed. Site live with paper links, author names, and About page.

**Next steps:**

1. Verify Vercel deployment picked up the changes
2. Create anchor document for next edition week
3. Wire `ClientPool` and `PipelineCache` into module functions

---

### 2026-03-07 19:49 — Dual-Depth Article Architecture

**What was done:**

- Added `signal_block` field to `Piece` dataclass (`generate/writer.py`)
- Rewrote `GENERATION_SYSTEM_PROMPT`: capability-only hooks, signal block spec (3-question structure), section word budgets, audience ceiling hard rules, banned words, voice DO/NEVER, anti-patterns
- Upgraded `NARRATIVE_POTENTIAL_PROMPT` to 4-criterion weighted rubric (Surprise 30%, Concreteness 25%, Practitioner Relevance 25%, Results Reportability 20%) in `curate/score.py`
- Added 3 new style checks to `verify/style.py`: `check_hook_form()`, `check_numbers_in_results()`, `check_signal_block()`
- Upgraded Quick Takes from abstract-first-sentence fallback to LLM-generated (Haiku) finding-first format in `generate/edition.py`
- Updated `publish/web.py` and `publish/email.py` to render Signal Blocks and Issue Summary
- Updated `docs/STYLE_CONSTITUTION.md` to v1.1.0, logged DEC-006 in `docs/DECISIONS.md`
- Created `data/anchors/2026-W10.1.yaml`
- Ran W10.1 edition: 3 papers, all 3 passed style checks (0 errors), 2657 words, deployed to Vercel

**Key decisions:**

- Signal block is a separate field (not inside `content`) — rendered between hook and body, serves executive readers
- Issue Summary derived from signal_block first sentences — no extra LLM call needed
- Pipeline always re-ingests (no skip-ingest mode) — W10.1 picked fresh today's ArXiv papers, which is fine since still within W10 date range

**State:** All working. Site live at signal.hugohmacedo.com with new architecture. Hero figure extraction confirmed working (this run's lead paper had no extractable figures).

**Next steps:**

1. Add `--skip-ingest` flag to pipeline CLI for reusing cached papers
2. Wire `ClientPool` and `PipelineCache` into module functions
3. Set up failure alerting (Slack/email)
4. Test automated weekly GitHub Actions dispatch

---

### 2026-03-08 15:53 — Edition enrichment: hero figures + TOC

**What was done:**

- Added hero figures to all 3 lead articles in 2026-W10 edition (previously only first had one)
  - Memex: bar chart (24.2% vs 85.6% success rate) — `public/figures/2603.04257v1_fig3.png`
  - Vision: geometry problem illustration — `public/figures/2603.03825v1_fig7.png`
- Added table of contents with anchor links to edition pages (both static HTML and web.py template)
- Fixed hero figure restriction in `web.py` — was `if i == 0` (first piece only), now shows on all pieces
- Added `id="quick-takes"` to quick takes section for TOC linking

**Key decisions:**

- Selected most impactful single figure per paper (result chart for Memex, concrete example for Vision)
- Only committed used figures to git; unused extracted figures left untracked locally
- TOC uses CSS counters matching brutalist design

**State:** Edition 2026-W10 fully enriched (structured abstracts, hero figures x3, TOC). Template updated for future editions.

**Next steps:**

1. Verify Vercel deployment reflects TOC and new figures
2. Wire `ClientPool` and `PipelineCache` into module functions
3. Set up failure alerting (Slack/email)
4. Add `--skip-ingest` flag to pipeline CLI
