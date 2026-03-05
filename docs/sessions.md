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
