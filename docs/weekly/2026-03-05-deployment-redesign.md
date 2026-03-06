# Session: Vercel Deployment, Buttondown Integration & Brutalist Redesign

**Date**: 2026-03-05
**Project**: Signal (scipaper)

## What Was Done

- Deployed Signal to Vercel at signal.hugohmacedo.com (vercel.json, public/ directory, clean URL rewrites)
- Configured Buttondown integration (username `signalhhmacedo`, subscribe form, welcome email)
- Built custom `/subscribed.html` confirmation page with JS form submission (stays on-domain via `mode: 'no-cors'` fetch)
- Redesigned all pages with bold/typographic brutalist style:
  - Helvetica Neue chrome, Georgia serif for edition body
  - Thick 8px top rule, 4px dividers, red-orange `#e63b19` accent
  - Consistent design system across landing, subscribed, archive, and edition pages
- Updated all URL defaults to signal.hugohmacedo.com
- Cleaned up 17 unused imports across test suite

## Key Decisions

- Vercel over GitHub Pages — Hugo's domain already managed there
- Manual-first deploy workflow: generate locally, commit `public/`, push, Vercel auto-deploys
- Buttondown handles subscribers, analytics, and welcome email delivery
- JS fetch with `no-cors` for subscribe form to keep user on-domain with branded confirmation
- Bold/typographic brutalist chosen over raw/monospace or Swiss minimalism — fits Signal's identity as authoritative research translation

## Next Steps

- Implement remaining 7 pipeline stubs (ingest, score, pdf_parser, writer, edition, checker, email)
- Create sample anchor document in `data/anchors/`
- Set up `.env` with API keys (Anthropic, Semantic Scholar, Buttondown)
- Run first real edition end-to-end with live data

---

# Session: Paper Metadata Display + About Page

**Date**: 2026-03-05
**Project**: Signal (scipaper)

## What Was Done

- Added `paper_url` and `authors` fields to `Piece` dataclass — edition pages now show linked paper titles and author bylines
- Updated `generate_piece()` to populate metadata from `Paper` object (fallback to arxiv.org URL)
- Created "How It Works" About page explaining the full pipeline: paper selection, writing process, verification, style rules
- About page designed to build trust and credibility — focuses on methodology, not personal
- Added About link to all footer navigation across every page type (5 templates in web.py + 3 static files)
- All changes committed and pushed to main

## Key Decisions

- About page content derived from PRODUCT_SPEC.md and STYLE_CONSTITUTION.md — accurate representation of actual pipeline
- Four sections: What This Is, How Papers Are Selected, How Papers Are Written, What You Won't Find Here
- Paper title links use `pdf_url` with fallback to `arxiv.org/abs/{id}` — ensures every paper is clickable
- Authors displayed as comma-separated names below title with muted styling

## Next Steps

- Verify Vercel deployment reflects all changes
- Create anchor document for next edition week
- Wire `ClientPool` and `PipelineCache` into module functions
