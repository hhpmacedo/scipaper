# Session: Dual-Depth Article Architecture

**Date**: 2026-03-07
**Project**: Signal (scipaper)

## What Was Done

- Added `signal_block` field to `Piece` dataclass — a separate 2-3 sentence executive off-ramp rendered between hook and article body
- Rewrote `GENERATION_SYSTEM_PROMPT` with hard rules: capability-only hooks, signal block 3-question structure, section word budgets (hook ~20w, signal ~60w, problem ~150w, etc.), audience ceiling enforcement, banned word list, dual-frame limitations
- Upgraded `NARRATIVE_POTENTIAL_PROMPT` to 4-criterion weighted rubric: Surprise Factor (30%), Concreteness (25%), Practitioner Relevance (25%), Results Reportability (20%) — vague results now penalized
- Added 3 new style QA checks: `check_hook_form()` (rejects method-description hooks), `check_numbers_in_results()` (requires numeric metric in Results section), `check_signal_block()` (errors if missing or too short)
- Upgraded Quick Takes from abstract-first-sentence fallback to LLM-generated (Haiku) finding-first format with specific numbers
- Updated web and email publishers to render Signal Blocks and Issue Summary (derived from signal_block, no extra LLM call)
- Updated `STYLE_CONSTITUTION.md` to v1.1.0, logged DEC-006 in `DECISIONS.md`
- Ran W10.1 edition: 3 papers selected, all 3 passed style checks with 0 errors, 2657 words
- Deployed to Vercel — live at signal.hugohmacedo.com

## Key Decisions

- Signal block lives outside `content` — it's a separate field on `Piece`, allowing different rendering per context (web, email, potential future API)
- Issue Summary at the top of each edition is derived from the first sentence of each piece's `signal_block` — avoids an extra LLM call while giving executive readers a one-line preview per piece
- Pipeline always re-ingests from ArXiv (no skip-ingest flag) — W10.1 used today's papers, which is acceptable since they're within the W10 date window
- All three new style checks registered 0 errors on W10.1 — the new generation prompt is producing compliant output from first generation pass

## Next Steps

- Add `--skip-ingest` CLI flag to reuse cached papers without re-fetching ArXiv
- Wire `ClientPool` and `PipelineCache` into individual module functions
- Set up failure alerting (Slack/email on pipeline failure)
- Test automated weekly GitHub Actions dispatch with Vercel secrets
