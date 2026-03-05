# Vercel Static Deployment for Signal

**Date:** 2026-03-05
**Status:** Approved

## Overview

Deploy Signal's static web archive to Vercel, served at `signal.hugohmacedo.com`. Hugo's main domain (`hugohmacedo.com`) is already on Vercel, so this keeps all hosting in one place.

## How It Works

1. Hugo runs the pipeline locally -- generates `public/` directory
2. Generated files are committed and pushed to `main`
3. Vercel auto-deploys from `main`, serving `public/` as the site root
4. `signal.hugohmacedo.com` configured as custom domain in Vercel

## Files to Create/Modify

- **`vercel.json`** -- output directory, clean URL rewrites, content-type headers for feeds
- **No `.gitignore` change** -- `public/` must be committed for Vercel to deploy it
- **No build command** -- Vercel serves static files only

## vercel.json Configuration

- `outputDirectory: "public"` -- points Vercel at the generated output
- Clean URL rewrites: `/archive` -> `/archive.html`, `/rss` -> `/rss.xml`
- Correct content-type headers for RSS and JSON Feed

## DNS Setup (Manual)

- Add `signal.hugohmacedo.com` as custom domain in Vercel project settings
- CNAME `signal.hugohmacedo.com` -> `cname.vercel-dns.com`

## Workflow

```
python -m scipaper.publish  -->  git add public/  -->  git push  -->  Vercel deploys
```

## Future Upgrade Path

When the pipeline runs in GitHub Actions, replace the manual workflow with Vercel CLI deployment (`vercel deploy --prod`) triggered from the Action.
