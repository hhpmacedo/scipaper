# Phase 6: Polish & Launch — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a branded landing page with Buttondown subscribe form, restructure web archive navigation, update production URLs, and draft welcome email copy.

**Architecture:** Extend the existing `web.py` module with a `generate_landing_page()` function. Rename the current index page to archive. Update `generate_web_archive()` to produce both. Add `buttondown_username` to `WebConfig`. Update all URL defaults to `https://signal.hugohmacedo.com`.

**Tech Stack:** Python, HTML (inline CSS for email compatibility), Buttondown embed form API

---

### Task 1: Add `buttondown_username` to WebConfig

**Files:**

- Modify: `scipaper/publish/web.py:19-24`
- Test: `tests/test_web.py`

**Step 1: Write the failing test**

Add to `tests/test_web.py`:

```python
class TestWebConfig:
    def test_default_buttondown_username(self):
        config = WebConfig()
        assert config.buttondown_username == "signal"

    def test_custom_buttondown_username(self):
        config = WebConfig(buttondown_username="hugo")
        assert config.buttondown_username == "hugo"

    def test_default_site_url(self):
        config = WebConfig()
        assert config.site_url == "https://signal.hugohmacedo.com"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_web.py::TestWebConfig -v`
Expected: FAIL (no `buttondown_username` field, wrong default `site_url`)

**Step 3: Write minimal implementation**

In `scipaper/publish/web.py`, update the `WebConfig` dataclass:

```python
@dataclass
class WebConfig:
    """Web archive configuration."""
    output_dir: Path = Path("public")
    site_url: str = "https://signal.hugohmacedo.com"
    site_title: str = "Signal — AI Research for the Curious"
    buttondown_username: str = "signal"
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_web.py::TestWebConfig -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scipaper/publish/web.py tests/test_web.py
git commit -m "feat: add buttondown_username to WebConfig, update default site_url"
```

---

### Task 2: Rename index page to archive page

**Files:**

- Modify: `scipaper/publish/web.py:103-156` (the `generate_index_page` function)
- Test: `tests/test_web.py`

**Step 1: Write the failing test**

Add to `tests/test_web.py`:

```python
class TestGenerateArchivePage:
    def test_valid_html(self):
        editions = [make_edition()]
        html = generate_archive_page(editions)
        assert "<!DOCTYPE html>" in html

    def test_lists_editions(self):
        editions = [
            make_edition(week="2026-W10", issue_number=1),
            make_edition(week="2025-W11", issue_number=2),
        ]
        html = generate_archive_page(editions)
        assert "2026-W10" in html
        assert "2025-W11" in html

    def test_has_home_link(self):
        """Archive page should link back to the landing page."""
        config = WebConfig(site_url="https://signal.test")
        editions = [make_edition()]
        html = generate_archive_page(editions, config)
        assert 'href="https://signal.test"' in html or 'href="https://signal.test/"' in html
```

Update the import at the top of `tests/test_web.py` to include `generate_archive_page`:

```python
from scipaper.publish.web import (
    WebConfig,
    generate_archive_page,
    generate_edition_page,
    generate_index_page,  # keep for backwards compat if needed
    generate_json_feed,
    generate_rss_feed,
    generate_web_archive,
)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_web.py::TestGenerateArchivePage -v`
Expected: FAIL (no `generate_archive_page`)

**Step 3: Write minimal implementation**

In `scipaper/publish/web.py`, rename `generate_index_page` to `generate_archive_page`. Keep an alias for backward compatibility:

```python
def generate_archive_page(
    editions: List[Edition], config: Optional[WebConfig] = None
) -> str:
    """
    Generate archive page listing all editions.
    """
    config = config or WebConfig()

    edition_items = []
    for ed in editions:
        lead_title = ed.pieces[0].title if ed.pieces else "Edition"
        edition_items.append(
            f'<li>'
            f'<a href="{config.site_url}/editions/{ed.week}.html">'
            f'#{ed.issue_number} — {ed.week}</a>'
            f'<span class="lead">{escape(lead_title)}</span>'
            f' &middot; {len(ed.pieces)} pieces, {ed.total_words} words'
            f'</li>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Archive — {escape(config.site_title)}</title>
<link rel="alternate" type="application/rss+xml" title="Signal RSS" href="{config.site_url}/rss.xml">
<style>
body {{ font-family: Georgia, 'Times New Roman', serif; max-width: 700px; margin: 0 auto; padding: 20px; color: #1a1a1a; line-height: 1.7; }}
header {{ text-align: center; padding: 30px 0; border-bottom: 2px solid #333; }}
header h1 {{ margin: 0; font-size: 32px; }}
header p {{ color: #666; margin: 8px 0 0; }}
.editions {{ list-style: none; padding: 0; }}
.editions li {{ padding: 16px 0; border-bottom: 1px solid #eee; }}
.editions a {{ font-size: 18px; color: #1a1a1a; font-weight: 600; text-decoration: none; }}
.editions .lead {{ display: block; color: #555; font-size: 14px; margin-top: 4px; }}
footer {{ margin-top: 40px; text-align: center; color: #999; font-size: 13px; }}
</style>
</head>
<body>
<header>
<h1><a href="{config.site_url}" style="text-decoration: none; color: inherit;">Signal</a></h1>
<p>AI Research for the Curious — Archive</p>
</header>

<ul class="editions">
{"".join(edition_items)}
</ul>

<footer>
<nav><a href="{config.site_url}">Home</a> &middot; <a href="{config.site_url}/rss.xml">RSS</a> &middot; <a href="{config.site_url}/feed.json">JSON Feed</a></nav>
</footer>
</body>
</html>"""


# Backward compatibility alias
generate_index_page = generate_archive_page
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_web.py::TestGenerateArchivePage tests/test_web.py::TestGenerateIndexPage -v`
Expected: ALL PASS (both new and old tests, since alias keeps backward compat)

**Step 5: Commit**

```bash
git add scipaper/publish/web.py tests/test_web.py
git commit -m "refactor: rename generate_index_page to generate_archive_page"
```

---

### Task 3: Create landing page generator

**Files:**

- Modify: `scipaper/publish/web.py`
- Test: `tests/test_web.py`

**Step 1: Write the failing tests**

Add to `tests/test_web.py`:

```python
class TestGenerateLandingPage:
    def test_valid_html(self):
        editions = [make_edition()]
        html = generate_landing_page(editions)
        assert "<!DOCTYPE html>" in html
        assert "</html>" in html

    def test_contains_branding(self):
        html = generate_landing_page([make_edition()])
        assert "Signal" in html
        assert "AI Research for the Curious" in html

    def test_contains_subscribe_form(self):
        config = WebConfig(buttondown_username="testuser")
        html = generate_landing_page([make_edition()], config)
        assert '<form' in html
        assert 'buttondown.com/api/emails/embed-subscribe/testuser' in html
        assert 'type="email"' in html

    def test_contains_value_prop(self):
        html = generate_landing_page([make_edition()])
        assert "weekly" in html.lower()

    def test_contains_latest_edition_link(self):
        editions = [make_edition(week="2026-W10", issue_number=1)]
        config = WebConfig(site_url="https://signal.test")
        html = generate_landing_page(editions, config)
        assert "2026-W10" in html
        assert "signal.test/editions/2026-W10.html" in html

    def test_contains_archive_link(self):
        config = WebConfig(site_url="https://signal.test")
        html = generate_landing_page([make_edition()], config)
        assert "signal.test/archive.html" in html

    def test_contains_rss_link(self):
        config = WebConfig(site_url="https://signal.test")
        html = generate_landing_page([make_edition()], config)
        assert "rss.xml" in html

    def test_empty_editions(self):
        """Landing page should work with no editions yet."""
        html = generate_landing_page([])
        assert "Signal" in html
        assert '<form' in html
```

Update import to include `generate_landing_page`:

```python
from scipaper.publish.web import (
    WebConfig,
    generate_archive_page,
    generate_edition_page,
    generate_index_page,
    generate_json_feed,
    generate_landing_page,
    generate_rss_feed,
    generate_web_archive,
)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_web.py::TestGenerateLandingPage -v`
Expected: FAIL (no `generate_landing_page`)

**Step 3: Write minimal implementation**

Add to `scipaper/publish/web.py`:

```python
def generate_landing_page(
    editions: List[Edition], config: Optional[WebConfig] = None
) -> str:
    """
    Generate landing page with subscribe form and latest edition link.
    """
    config = config or WebConfig()

    # Latest edition section
    latest_html = ""
    if editions:
        latest = editions[0]
        lead_title = latest.pieces[0].title if latest.pieces else "Latest Edition"
        latest_html = (
            f'<section class="latest">'
            f'<h2>Latest Edition</h2>'
            f'<p><a href="{config.site_url}/editions/{latest.week}.html">'
            f'#{latest.issue_number} — {latest.week}: {escape(lead_title)}</a></p>'
            f'</section>'
        )

    subscribe_url = f"https://buttondown.com/api/emails/embed-subscribe/{config.buttondown_username}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape(config.site_title)}</title>
<link rel="alternate" type="application/rss+xml" title="Signal RSS" href="{config.site_url}/rss.xml">
<link rel="alternate" type="application/json" title="Signal JSON Feed" href="{config.site_url}/feed.json">
<style>
body {{ font-family: Georgia, 'Times New Roman', serif; max-width: 700px; margin: 0 auto; padding: 20px; color: #1a1a1a; line-height: 1.7; }}
header {{ text-align: center; padding: 60px 0 40px; }}
header h1 {{ margin: 0; font-size: 48px; letter-spacing: -1px; }}
header p {{ color: #555; margin: 8px 0 0; font-size: 18px; }}
.value-prop {{ max-width: 540px; margin: 0 auto; padding: 20px 0; }}
.value-prop ul {{ padding-left: 20px; }}
.value-prop li {{ margin-bottom: 8px; }}
.subscribe {{ text-align: center; padding: 40px 0; border-top: 1px solid #eee; border-bottom: 1px solid #eee; margin: 30px 0; }}
.subscribe h2 {{ font-size: 22px; margin-bottom: 16px; }}
.subscribe form {{ display: flex; justify-content: center; gap: 8px; flex-wrap: wrap; }}
.subscribe input[type="email"] {{ padding: 10px 16px; font-size: 16px; border: 1px solid #ccc; border-radius: 4px; width: 280px; font-family: inherit; }}
.subscribe input[type="submit"] {{ padding: 10px 24px; font-size: 16px; background: #1a1a1a; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-family: inherit; }}
.subscribe input[type="submit"]:hover {{ background: #333; }}
.latest {{ text-align: center; padding: 20px 0; }}
.latest h2 {{ font-size: 18px; color: #666; margin-bottom: 8px; }}
.latest a {{ color: #1a1a1a; font-weight: 600; text-decoration: none; }}
.latest a:hover {{ text-decoration: underline; }}
footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; text-align: center; color: #999; font-size: 13px; }}
footer a {{ color: #666; margin: 0 8px; }}
</style>
</head>
<body>
<header>
<h1>Signal</h1>
<p>AI Research for the Curious</p>
</header>

<div class="value-prop">
<p>A weekly newsletter that translates the most important AI research papers into clear, rigorous prose. No hype. No jargon. Every claim grounded in the source.</p>
<ul>
<li>3-5 papers weekly, each ~800-1200 words</li>
<li>Written for engineers, PMs, and founders who use AI but don't read papers</li>
<li>Delivered every Tuesday</li>
</ul>
</div>

<div class="subscribe">
<h2>Subscribe — it's free</h2>
<form action="{subscribe_url}" method="post">
<input type="email" name="email" placeholder="you@example.com" required>
<input type="submit" value="Subscribe">
</form>
</div>

{latest_html}

<footer>
<nav><a href="{config.site_url}/archive.html">Archive</a> <a href="{config.site_url}/rss.xml">RSS</a></nav>
</footer>
</body>
</html>"""
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_web.py::TestGenerateLandingPage -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add scipaper/publish/web.py tests/test_web.py
git commit -m "feat: add landing page with Buttondown subscribe form"
```

---

### Task 4: Update `generate_web_archive()` to produce landing + archive

**Files:**

- Modify: `scipaper/publish/web.py:159-200` (the `generate_web_archive` function)
- Modify: `tests/test_web.py`

**Step 1: Write the failing test**

Update the `TestGenerateWebArchive` class in `tests/test_web.py`:

```python
class TestGenerateWebArchive:
    def test_creates_files(self, tmp_path):
        config = WebConfig(output_dir=tmp_path / "public")
        editions = [make_edition()]

        output = run_async(generate_web_archive(editions, config))

        assert (output / "index.html").exists()
        assert (output / "archive.html").exists()
        assert (output / "editions" / "2026-W10.html").exists()
        assert (output / "rss.xml").exists()
        assert (output / "feed.json").exists()

    def test_index_is_landing_page(self, tmp_path):
        """index.html should be the landing page with subscribe form."""
        config = WebConfig(output_dir=tmp_path / "public", buttondown_username="testuser")
        editions = [make_edition()]

        output = run_async(generate_web_archive(editions, config))

        index_html = (output / "index.html").read_text()
        assert "buttondown.com/api/emails/embed-subscribe/testuser" in index_html

    def test_archive_lists_editions(self, tmp_path):
        """archive.html should list all editions."""
        config = WebConfig(output_dir=tmp_path / "public")
        editions = [make_edition(week="2026-W10", issue_number=1)]

        output = run_async(generate_web_archive(editions, config))

        archive_html = (output / "archive.html").read_text()
        assert "2026-W10" in archive_html

    def test_multiple_editions(self, tmp_path):
        config = WebConfig(output_dir=tmp_path / "public")
        editions = [
            make_edition(week="2026-W10", issue_number=1),
            make_edition(week="2025-W11", issue_number=2),
        ]

        output = run_async(generate_web_archive(editions, config))

        assert (output / "editions" / "2026-W10.html").exists()
        assert (output / "editions" / "2025-W11.html").exists()

        archive = (output / "archive.html").read_text()
        assert "2026-W10" in archive
        assert "2025-W11" in archive
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_web.py::TestGenerateWebArchive -v`
Expected: FAIL (`archive.html` doesn't exist, `index.html` is still the edition list)

**Step 3: Write minimal implementation**

Update `generate_web_archive` in `scipaper/publish/web.py`:

```python
async def generate_web_archive(
    editions: List[Edition], config: Optional[WebConfig] = None
) -> Path:
    """
    Generate complete static web archive.

    Creates:
    - index.html (landing page with subscribe form)
    - archive.html (edition list)
    - /editions/2026-W10.html (individual editions)
    - /rss.xml (RSS feed)
    - /feed.json (JSON feed)

    Returns path to output directory.
    """
    config = config or WebConfig()
    output = config.output_dir
    output.mkdir(parents=True, exist_ok=True)

    editions_dir = output / "editions"
    editions_dir.mkdir(exist_ok=True)

    # Generate landing page
    landing_html = generate_landing_page(editions, config)
    (output / "index.html").write_text(landing_html)

    # Generate archive
    archive_html = generate_archive_page(editions, config)
    (output / "archive.html").write_text(archive_html)

    # Generate edition pages
    for edition in editions:
        page_html = generate_edition_page(edition, config)
        (editions_dir / f"{edition.week}.html").write_text(page_html)

    # Generate feeds
    rss = generate_rss_feed(editions, config)
    (output / "rss.xml").write_text(rss)

    json_feed = generate_json_feed(editions, config)
    (output / "feed.json").write_text(json_feed)

    logger.info(
        f"Generated web archive: {len(editions)} editions to {output}"
    )

    return output
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_web.py::TestGenerateWebArchive -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add scipaper/publish/web.py tests/test_web.py
git commit -m "feat: generate landing page + archive in web archive"
```

---

### Task 5: Update edition page navigation

**Files:**

- Modify: `scipaper/publish/web.py:27-100` (the `generate_edition_page` function)
- Test: `tests/test_web.py`

**Step 1: Write the failing test**

Add to `tests/test_web.py` in the `TestGenerateEditionPage` class:

```python
    def test_has_archive_link(self):
        config = WebConfig(site_url="https://signal.test")
        edition = make_edition()
        html = generate_edition_page(edition, config)
        assert 'signal.test/archive.html' in html

    def test_has_home_link(self):
        config = WebConfig(site_url="https://signal.test")
        edition = make_edition()
        html = generate_edition_page(edition, config)
        assert 'href="https://signal.test"' in html or 'href="https://signal.test/"' in html
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_web.py::TestGenerateEditionPage::test_has_archive_link -v`
Expected: FAIL (currently links to `Archive` pointing to site root, not `/archive.html`)

**Step 3: Write minimal implementation**

In `generate_edition_page`, update the footer nav:

Change:

```python
<nav><a href="{config.site_url}">Archive</a> <a href="{config.site_url}/rss.xml">RSS</a></nav>
```

To:

```python
<nav><a href="{config.site_url}">Home</a> <a href="{config.site_url}/archive.html">Archive</a> <a href="{config.site_url}/rss.xml">RSS</a></nav>
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_web.py::TestGenerateEditionPage -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add scipaper/publish/web.py tests/test_web.py
git commit -m "feat: update edition page nav with home and archive links"
```

---

### Task 6: Update URL defaults across codebase

**Files:**

- Modify: `scipaper/pipeline.py:50`
- Modify: `scipaper/__main__.py:58`
- Modify: `.github/workflows/weekly-edition.yml:31`
- Test: `tests/test_cli.py`

**Step 1: Write the failing test**

Add to `tests/test_cli.py`:

```python
def test_default_web_url_is_production():
    """Default web URL should be the production URL."""
    from scipaper.pipeline import PipelineConfig
    config = PipelineConfig()
    assert config.web_base_url == "https://signal.hugohmacedo.com"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py::test_default_web_url_is_production -v`
Expected: FAIL (current default is `https://signal.example.com`)

**Step 3: Write minimal implementation**

In `scipaper/pipeline.py` line 50, change:

```python
    web_base_url: str = "https://signal.example.com"
```

To:

```python
    web_base_url: str = "https://signal.hugohmacedo.com"
```

In `scipaper/__main__.py` line 58, change:

```python
        web_base_url=os.environ.get("SIGNAL_WEB_URL", "https://signal.example.com"),
```

To:

```python
        web_base_url=os.environ.get("SIGNAL_WEB_URL", "https://signal.hugohmacedo.com"),
```

In `.github/workflows/weekly-edition.yml` line 31, change:

```yaml
SIGNAL_WEB_URL: ${{ secrets.SIGNAL_WEB_URL }}
```

To:

```yaml
SIGNAL_WEB_URL: "https://signal.hugohmacedo.com"
```

(Use the real URL directly instead of a secret — it's not sensitive.)

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py::test_default_web_url_is_production -v`
Expected: PASS

Also run the full web test suite to check nothing broke:

Run: `pytest tests/test_web.py -v`
Expected: ALL PASS (note: tests that used explicit `WebConfig(site_url="...")` are unaffected; tests that used defaults may now see the new URL — verify)

**Step 5: Commit**

```bash
git add scipaper/pipeline.py scipaper/__main__.py .github/workflows/weekly-edition.yml tests/test_cli.py
git commit -m "feat: update default URLs to signal.hugohmacedo.com"
```

---

### Task 7: Draft welcome email copy

**Files:**

- Create: `docs/welcome-email.md`

**Step 1: Create the welcome email**

```markdown
# Welcome to Signal

Subject: Welcome to Signal — here's what to expect

---

Thanks for subscribing to Signal.

Every Tuesday, you'll receive 3-5 pieces translating the most important AI research papers into clear, rigorous prose. No hype. No jargon. Every claim grounded in the original paper.

Each piece follows a simple structure: what problem the researchers tackled, what they actually did, what worked (and what didn't), and why it matters to you.

You can browse all past editions in the archive:
https://signal.hugohmacedo.com/archive.html

If you have feedback, just reply to any edition — I read everything.

— Hugo
```

**Step 2: Commit**

```bash
git add docs/welcome-email.md
git commit -m "docs: draft welcome email copy for Buttondown"
```

---

### Task 8: Run full test suite and lint

**Step 1: Run all tests**

Run: `pytest -v`
Expected: ALL PASS (should be ~195+ tests)

**Step 2: Run linter**

Run: `ruff check scipaper/ tests/test_web.py tests/test_cli.py`
Expected: No errors in modified files

**Step 3: Fix any issues found**

If linter finds issues, fix them.

**Step 4: Commit fixes if any**

```bash
git add -A
git commit -m "fix: clean up lint issues from Phase 6"
```

---

### Task 9: Update CLAUDE.md and PHASES.md

**Files:**

- Modify: `CLAUDE.md`
- Modify: `docs/PHASES.md`

**Step 1: Update CLAUDE.md project status**

Update the `Current focus` and `Next steps`:

```markdown
- **Current focus**: Phases 0-6 fully implemented. All 195+ tests pass. Landing page with Buttondown subscribe form, welcome email drafted, production URLs configured.
- **Next steps**:
  1. Configure Buttondown account (create, set username, paste welcome email)
  2. Set up DNS for signal.hugohmacedo.com
  3. Deploy static site and run first real edition end-to-end
```

**Step 2: Update PHASES.md checkboxes**

Mark Phase 6 deliverables as done:

- [x] Landing page with signup
- [x] Welcome email sequence
- [ ] First public edition (requires live run)
- [ ] Basic analytics (Buttondown built-in, no code needed)

**Step 3: Commit**

```bash
git add CLAUDE.md docs/PHASES.md
git commit -m "docs: update project status for Phase 6 completion"
```
