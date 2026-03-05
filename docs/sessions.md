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
