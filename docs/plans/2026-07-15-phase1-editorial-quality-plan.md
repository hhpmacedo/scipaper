# Phase 1 — Editorial & Writing Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the next edition a reader opens read tighter, less repetitive, and less formulaic — by removing the hook duplication, the mandated "1–2 years" and maturity-spectrum tics, and making the dual-layer "Why It Matters" real — all within the fully-autonomous constraint (prompt + Style Constitution + renderer changes only).

**Architecture:** Three mechanical, deterministic changes (strip the duplicated hook at render time; add a deterministic style gate for it; enforce an edition length budget) plus two prompt/Constitution changes (timeline/maturity become *optional not mandated*; "Why It Matters" explicitly serves builder + decision-maker). Mechanical changes are TDD'd; prompt/doc changes are verified by inspection + a sample regeneration.

**Tech Stack:** Python 3.14, pytest, dataclasses. LLM prompts are plain strings in `writer.py`/`verify/style.py`. Renderers are string-building functions in `publish/web.py` and `publish/email.py`.

---

## Pre-existing state (baseline — verify before starting)

Run `python -m pytest tests/ -q`. Known RED before this plan (NOT caused by us; do not treat as regressions):

1. **`tests/test_style.py` — cannot collect.** It imports `check_banned_words, check_citations, check_structure, check_word_count` from `scipaper.verify.style`, which were removed when `style.py` was refactored to the LLM-based checker. **Task 5 reconciles this file.**
2. **`tests/test_email.py::TestSendEditionEmail::test_sends_to_buttondown_api` — 1 failure** (`assert 'about_to_send' == 'draft'`), stale after the "send weekly email automatically instead of creating a draft" change. **Out of scope for Phase 1** — leave it; note it in the final report.

Everything else (83 tests) is GREEN. Requirements are installed via `pip install -r requirements.txt`.

## File structure

| File | Responsibility | Task |
|---|---|---|
| `docs/STYLE_CONSTITUTION.md` | Amend to v1.2.0: timeline/maturity optional, "state each number once", dual-layer Why-It-Matters, edition length budget | 1 |
| `docs/DECISIONS.md` | Log the amendment (its own amendment rule requires this) | 1 |
| `scipaper/text_utils.py` | New shared helper `strip_leading_hook(content, hook)` | 2 |
| `scipaper/publish/web.py` | Apply `strip_leading_hook` before rendering content | 3 |
| `scipaper/publish/email.py` | Apply `strip_leading_hook` before rendering content | 3 |
| `scipaper/generate/writer.py` | Prompt: content starts at `## The Problem`; timeline/maturity optional; dual-layer Why-It-Matters | 4 |
| `scipaper/verify/style.py` | Public `check_banned_words`/`check_word_count`; new `check_repeated_hook`; updated LLM rules | 5 |
| `scipaper/generate/edition.py` | `check_edition_length(edition)` warning helper | 6 |
| `tests/test_text_utils.py` | Tests for `strip_leading_hook` | 2 |
| `tests/test_web.py`, `tests/test_email.py` | Tests that rendered content has no duplicated hook | 3 |
| `tests/test_style.py` | Reconcile to current API + tests for `check_repeated_hook` | 5 |
| `tests/test_edition.py` | Test for `check_edition_length` | 6 |

---

## Task 1: Style Constitution amendment (v1.1.0 → v1.2.0)

**Files:**
- Modify: `docs/STYLE_CONSTITUTION.md`
- Modify: `docs/DECISIONS.md`

This is a documentation task — no code test. Verification is inspection.

- [ ] **Step 1: Bump the version header**

In `docs/STYLE_CONSTITUTION.md`, change:
```
**Version:** 1.1.0
```
to:
```
**Version:** 1.2.0
```
and update `**Last Updated:**` to `2026-07-15`.

- [ ] **Step 2: Make the production-timeline optional (fixes the "1–2 years" tic)**

In the `### 5. The Results` section, find:
```
Every limitation must be dual-framed:

- Technical dimension (for builders): what's incomplete about the methodology
- Production timeline dimension (for decision-makers): what this means for applicability
- ❌ "The benchmark covers only four LLMs and four languages."
- ✅ "The benchmark covers only four LLMs and four languages — production codebases with mixed model usage and human edits are a harder problem, likely 2-3 years from reliable tooling."
```
Replace with:
```
Frame limitations for both audiences, but do NOT invent a numeric timeline:

- Technical dimension (for builders): what's incomplete about the methodology — always state this concretely.
- Production dimension (for decision-makers): what would have to be true for this to be usable. Name the *gap*, not a fabricated number of years.
- Include a specific "years to production" estimate ONLY when the paper itself discusses deployment maturity or a concrete adoption barrier. Otherwise describe the gap qualitatively.
- ❌ "The benchmark covers only four LLMs and four languages — likely 2-3 years from reliable tooling." (invented timeline)
- ✅ "The benchmark covers only four LLMs and four languages; production codebases mix models and human edits, which this setup doesn't test." (names the gap, no fake number)

**Do not end every limitations section with a "1–2 years out" clause. If you find yourself writing the same timeline phrase across pieces, cut it.**
```

- [ ] **Step 3: Make the maturity-spectrum sentence optional**

In the `### 6. Why It Matters` section, find:
```
Include one sentence positioning the work on the maturity spectrum: lab proof-of-concept, pattern emerging in production frameworks, or actionable today.
```
Replace with:
```
Where it genuinely aids the reader, position the work on the maturity spectrum (lab proof-of-concept / pattern emerging / actionable today). This is allowed, not required — do NOT open every "Why It Matters" with "This is a lab proof-of-concept." Vary how maturity is conveyed, or let the limitations carry it.
```

- [ ] **Step 4: Add the dual-layer "Why It Matters" rule**

In the `### 6. Why It Matters` section, after the first line (`Implications for practitioners...`), add:
```

**Serve two readers explicitly.** This section must land for both:
- a **builder** (what they could try, test, or adopt), and
- a **non-builder decision-maker** (what it changes about cost, risk, capability, or timing for their org).
At least one sentence must speak to each. Do NOT address only "teams building [niche infra]" — most readers are not building the paper's system.
```

- [ ] **Step 5: Add "state each key number once" to the dedup law**

In the `## Voice` → `### Never` list, find:
```
- Explain the same concept twice across sections.
```
Add immediately after it:
```
- State the same headline number more than once across the hook, signal block, and structured abstract. Pick the single strongest place for each number. (The Results section may restate a number with its baseline — that's where the number is *explained*, not just asserted.)
- Repeat the hook as the opening line of the article body. The article body starts at "## The Problem". The hook is rendered separately.
```

- [ ] **Step 6: Add the edition length budget**

In the `## Length` section, after the `Headlines` bullet, add:
```

**Per edition:** target ≈ 2,500–3,000 words total across all feature pieces (≈12-minute read). If an edition exceeds this, tighten the longest pieces first; do not cut the number of pieces below three.
```

- [ ] **Step 7: Log the decision**

Append to `docs/DECISIONS.md` a new entry using the existing template:
```markdown
### DEC-011: Style Constitution v1.2.0 — de-templatize editorial voice

**Status:** RESOLVED
**Priority:** HIGH
**Owner:** Hugo

**Context:**
Reader-lens review of #16–#18 found the prose had become formulaic: a
mandated production-timeline produced a reflexive "1–2 years out" clause on
nearly every limitation; a mandated maturity sentence made every "Why It
Matters" open with "lab proof-of-concept"; the hook was repeated verbatim as
the article's opening paragraph; headline numbers were restated 3–4 times; and
implications addressed only niche-infra builders rather than the actual reader.

**Decision:**
Amend the Style Constitution to v1.2.0: production-timeline and maturity-spectrum
sentences become optional (allowed only when grounded), add a "state each number
once" rule, forbid repeating the hook in the body, require dual-layer
(builder + decision-maker) "Why It Matters", and add a per-edition length budget.

**Rationale:**
These tics all trace to *mandatory* prompt instructions, not to any editorial
need. Making them optional and machine-checkable removes the sameness without a
human review step. Part of the Phase 1 editorial-quality work (see
docs/plans/2026-07-15-editorial-improvement-plan.md).
```

- [ ] **Step 8: Commit**

```bash
git add docs/STYLE_CONSTITUTION.md docs/DECISIONS.md
git commit -m "docs: Style Constitution v1.2.0 — de-templatize editorial voice"
```

---

## Task 2: `strip_leading_hook` helper

The hook is duplicated because the LLM writes the hook as the article body's first paragraph AND it's rendered separately from `piece.hook`. This helper removes the duplicate defensively at render time (works even on already-stored editions). Task 4 also stops new generations from producing it.

**Files:**
- Modify: `scipaper/text_utils.py`
- Test: `tests/test_text_utils.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_text_utils.py`:
```python
from scipaper.text_utils import strip_leading_hook


def test_strip_leading_hook_removes_duplicated_hook():
    hook = "You can now identify which AI wrote a snippet with 87% accuracy."
    content = (
        "You can now identify which AI wrote a snippet with 87% accuracy.\n\n"
        "## The Problem\nAttribution is hard [§1]."
    )
    result = strip_leading_hook(content, hook)
    assert result.startswith("## The Problem")
    assert "87% accuracy" not in result.split("## The Problem")[0]


def test_strip_leading_hook_leaves_clean_content_untouched():
    hook = "You can now identify which AI wrote a snippet."
    content = "## The Problem\nAttribution is hard [§1]."
    assert strip_leading_hook(content, hook) == content


def test_strip_leading_hook_matches_despite_whitespace_and_case():
    hook = "A single misleading document can override five accurate ones."
    content = (
        "A single   misleading document can override five accurate ones.\n\n"
        "## The Problem\nRAG is messy."
    )
    assert strip_leading_hook(content, hook).startswith("## The Problem")


def test_strip_leading_hook_does_not_strip_long_paragraph():
    # A real Problem paragraph that merely shares opening words must survive.
    hook = "Models fail on noisy inputs."
    content = (
        "Models fail on noisy inputs in ways that matter enormously for anyone "
        "shipping to production, and this section explains exactly why that "
        "happens across a dozen distinct failure modes that compound.\n\n"
        "## The Problem\nMore detail."
    )
    assert strip_leading_hook(content, hook) == content


def test_strip_leading_hook_handles_empty():
    assert strip_leading_hook("", "hook") == ""
    assert strip_leading_hook("content", "") == "content"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_text_utils.py -k strip_leading_hook -v`
Expected: FAIL with `ImportError: cannot import name 'strip_leading_hook'`

- [ ] **Step 3: Implement the helper**

Add to `scipaper/text_utils.py`:
```python
import re


def strip_leading_hook(content: str, hook: str) -> str:
    """
    Remove a leading paragraph that duplicates the hook.

    The generator sometimes emits the hook as the article body's opening
    paragraph, while the hook is also rendered separately. This strips that
    duplicate so it appears once. Content that does not start with the hook
    is returned unchanged.
    """
    if not content or not hook:
        return content

    def _norm(s: str) -> str:
        return re.sub(r"\s+", " ", s).strip().lower()

    stripped = content.lstrip()
    # The leading block is everything before the first blank line or heading.
    boundary = re.search(r"\n\s*\n|\n(?=#{1,6}\s)", stripped)
    if boundary:
        lead = stripped[: boundary.start()]
        rest = stripped[boundary.end():]
    else:
        lead, rest = stripped, ""

    # Only a short lead can be a hook (hooks are ~20 words); protects real paragraphs.
    if len(lead.split()) > 40:
        return content

    lead_n, hook_n = _norm(lead), _norm(hook)
    if lead_n and (lead_n == hook_n or lead_n.startswith(hook_n) or hook_n.startswith(lead_n)):
        return rest.lstrip()
    return content
```
(If `import re` already exists at the top of `text_utils.py`, don't duplicate it.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_text_utils.py -k strip_leading_hook -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add scipaper/text_utils.py tests/test_text_utils.py
git commit -m "feat: add strip_leading_hook helper to de-duplicate hook at render time"
```

---

## Task 3: Apply dedup in the renderers

**Files:**
- Modify: `scipaper/publish/web.py:185` (the `content_html = _content_to_html(piece.content)` line)
- Modify: `scipaper/publish/email.py` (both full and preview renderers that use `piece.content`)
- Test: `tests/test_web.py`, `tests/test_email.py`

- [ ] **Step 1: Write the failing test (web)**

Add to `tests/test_web.py` (reuse the module's existing edition/piece fixtures; if it has a `make_piece`/`make_edition` helper, use it — otherwise construct a `Piece` as `tests/test_style.py` does):
```python
def test_rendered_html_does_not_duplicate_hook():
    from scipaper.publish.web import generate_edition_page, WebConfig
    from scipaper.generate.writer import Piece
    from scipaper.generate.edition import Edition

    piece = Piece(
        paper_id="2607.00001",
        title="Test Title Here For Piece",
        hook="Models fail on most realistic tasks.",
        content=(
            "Models fail on most realistic tasks.\n\n"
            "## The Problem\nBenchmarks are idealized [§1].\n\n"
            "## What They Did\nThey de-idealized them [§2].\n\n"
            "## The Results\nGPT-5 scored 44% [§3].\n\n"
            "## Why It Matters\nExpect lower success [§4]."
        ),
        word_count=30,
        citations=[],
        generated_at="2026-07-15T00:00:00",
        model_used="test",
    )
    edition = Edition(week="2026-W29", issue_number=18, pieces=[piece], quick_takes=[])
    html = generate_edition_page(edition, WebConfig())
    # The hook string must appear exactly once (in the <p class="hook">), not again in body.
    assert html.count("Models fail on most realistic tasks.") == 1
```
(Match `Edition(...)` constructor args to the real signature in `scipaper/generate/edition.py`; adjust `quick_takes`/kwargs as needed.)

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_web.py::test_rendered_html_does_not_duplicate_hook -v`
Expected: FAIL — count is 2 (hook rendered twice).

- [ ] **Step 3: Implement (web)**

In `scipaper/publish/web.py`, change line 185 from:
```python
        content_html = _content_to_html(piece.content)
```
to:
```python
        content_html = _content_to_html(strip_leading_hook(piece.content, piece.hook))
```
Add the import near the top of `web.py` (with the other `from ..` imports):
```python
from ..text_utils import strip_leading_hook
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_web.py::test_rendered_html_does_not_duplicate_hook -v`
Expected: PASS

- [ ] **Step 5: Write the failing test (email)**

Add to `tests/test_email.py` (use the same `Piece`/`Edition` construction as Step 1):
```python
def test_email_html_does_not_duplicate_hook():
    from scipaper.publish.email import render_edition_html
    from scipaper.generate.writer import Piece
    from scipaper.generate.edition import Edition

    piece = Piece(
        paper_id="2607.00001",
        title="Test Title Here For Piece",
        hook="Models fail on most realistic tasks.",
        content=(
            "Models fail on most realistic tasks.\n\n"
            "## The Problem\nBenchmarks are idealized [§1].\n\n"
            "## What They Did\nThey de-idealized them [§2].\n\n"
            "## The Results\nGPT-5 scored 44% [§3].\n\n"
            "## Why It Matters\nExpect lower success [§4]."
        ),
        word_count=30,
        citations=[],
        generated_at="2026-07-15T00:00:00",
        model_used="test",
    )
    edition = Edition(week="2026-W29", issue_number=18, pieces=[piece], quick_takes=[])
    html = render_edition_html(edition)
    assert html.count("Models fail on most realistic tasks.") == 1
```

- [ ] **Step 6: Run to verify it fails**

Run: `python -m pytest tests/test_email.py::test_email_html_does_not_duplicate_hook -v`
Expected: FAIL — count is 2.

- [ ] **Step 7: Implement (email)**

In `scipaper/publish/email.py`, add the import:
```python
from ..text_utils import strip_leading_hook
```
Then in the full-content piece renderer (the function around line 89 that renders `piece.content`), replace the point where `piece.content` is converted to HTML with `strip_leading_hook(piece.content, piece.hook)`. If the preview renderer (around line 111) uses the *first paragraph* of `piece.content` as the preview, apply `strip_leading_hook` there too so the preview isn't the duplicated hook:
```python
    body = strip_leading_hook(piece.content, piece.hook)
    # ...use `body` wherever piece.content was previously converted/split.
```
(Inspect the two renderers and route both through `body`.)

- [ ] **Step 8: Run to verify it passes**

Run: `python -m pytest tests/test_email.py::test_email_html_does_not_duplicate_hook -v`
Expected: PASS

- [ ] **Step 9: Run the render suites for regressions**

Run: `python -m pytest tests/test_web.py tests/test_email.py -q`
Expected: all pass except the known pre-existing `test_sends_to_buttondown_api` failure.

- [ ] **Step 10: Commit**

```bash
git add scipaper/publish/web.py scipaper/publish/email.py tests/test_web.py tests/test_email.py
git commit -m "fix: strip duplicated hook paragraph from rendered content (web + email)"
```

---

## Task 4: Generation prompt changes (writer.py)

Stops *new* generations from producing the hook duplication and the tics. Prompt text is not deterministically unit-testable; verification is inspection (Step 5) plus the sample regeneration in Task 7.

**Files:**
- Modify: `scipaper/generate/writer.py`

- [ ] **Step 1: Stop the body from repeating the hook**

In `GENERATION_SYSTEM_PROMPT`, in the `RETURN FORMAT` JSON block, change:
```
  "content": "the full piece with citations — Hook paragraph, then ## The Problem, ## What They Did, ## The Results, ## Why It Matters",
```
to:
```
  "content": "the full piece with citations — START at ## The Problem (do NOT repeat the hook as an opening paragraph), then ## What They Did, ## The Results, ## Why It Matters",
```

- [ ] **Step 2: Add an explicit no-repeat rule near the hook definition**

In `GENERATION_SYSTEM_PROMPT`, after the `1. Hook` block (ending with the GOOD example line), add:
```
   - The hook appears ONLY in the "hook" field. Do NOT restate it as the first paragraph of "content". The content begins at "## The Problem".
```

- [ ] **Step 3: Make the production-timeline optional (kills the "1–2 years" tic)**

In `GENERATION_SYSTEM_PROMPT`, section `5. The Results`, replace:
```
   - Every limitation must be dual-framed: what's technically incomplete (for builders) AND what that means for production timelines (for decision-makers).
   - BAD: "The benchmark covers only four LLMs and four languages."
   - GOOD: "The benchmark covers only four LLMs and four languages — production codebases with mixed model usage and human edits are a harder problem, likely 2-3 years from reliable tooling."
```
with:
```
   - Frame each limitation for builders (what's technically incomplete) AND decision-makers (what would have to be true to use it) — but do NOT invent a numeric timeline. Give a "years to production" number ONLY if the paper discusses deployment maturity.
   - BAD: "...likely 2-3 years from reliable tooling." (fabricated timeline appended to every limitation)
   - GOOD: "The benchmark covers only four LLMs and four languages; production codebases mix models and human edits, which this setup doesn't test." (names the gap, no invented number)
   - Avoid ending every limitations passage with the same timeline phrasing.
```

- [ ] **Step 4: Make the maturity sentence optional + require dual-layer Why It Matters**

In `GENERATION_SYSTEM_PROMPT`, section `6. Why It Matters`, replace:
```
   - Implications for practitioners. Grounded, not speculative.
   - Include one sentence positioning the work on a maturity spectrum: lab proof-of-concept, pattern emerging in production frameworks, or actionable today.
   - Every implication must trace back to something the paper demonstrated.
```
with:
```
   - Implications, grounded, not speculative. Serve TWO readers explicitly: at least one sentence for a builder (what to try/test/adopt) AND at least one for a non-builder decision-maker (what it changes about cost, risk, capability, or timing for their org). Do NOT address only "teams building [the paper's niche system]".
   - Positioning on the maturity spectrum (lab proof-of-concept / emerging / actionable) is ALLOWED but NOT required — do not open every piece with "This is a lab proof-of-concept." Vary it or let the limitations carry it.
   - Every implication must trace back to something the paper demonstrated.
```

- [ ] **Step 5: Update the user-prompt reminders**

In `GENERATION_USER_PROMPT`, replace:
```
- Every limitation dual-framed: technical gap + production timeline implication
```
with:
```
- Content starts at ## The Problem (never repeat the hook as an opening paragraph)
- Limitations: name the technical gap + what it means for use; no invented "X years" timeline unless the paper discusses maturity
- Why It Matters serves a builder AND a decision-maker
```

- [ ] **Step 6: Verify by inspection**

Re-read `GENERATION_SYSTEM_PROMPT` and `GENERATION_USER_PROMPT`. Confirm: (a) no instruction tells the model to put the hook in `content`; (b) the timeline is conditional; (c) the maturity sentence is optional; (d) dual-layer is required. Run `python -m pytest tests/test_writer.py -q` — expected: still green (these are prompt-string edits; existing writer tests should not depend on the changed phrases; if one asserts on old prompt text, update that assertion to the new text).

- [ ] **Step 7: Commit**

```bash
git add scipaper/generate/writer.py tests/test_writer.py
git commit -m "feat: de-templatize generation prompt (no hook-in-body, optional timeline/maturity, dual-layer why-it-matters)"
```

---

## Task 5: Style checker — reconcile tests + deterministic hook-dup gate

**Files:**
- Modify: `scipaper/verify/style.py`
- Modify: `tests/test_style.py` (reconcile broken imports)

- [ ] **Step 1: Expose deterministic helpers + add the hook-dup check**

In `scipaper/verify/style.py`, add these public functions (near `_check_banned_words`):
```python
from typing import Optional  # if not already imported


def check_banned_words(content: str) -> List[StyleIssue]:
    """Public wrapper: fast local banned/caution word check."""
    return _check_banned_words(content)


def check_word_count(content: str, config: Optional["StyleConfig"] = None) -> tuple:
    """Public wrapper: returns (word_count, ok)."""
    return _check_word_count(content, config or StyleConfig())


def check_repeated_hook(piece: Piece) -> Optional[StyleIssue]:
    """Error if the hook is repeated as the opening paragraph of the content."""
    from ..text_utils import strip_leading_hook
    if not piece.hook or not piece.content:
        return None
    if strip_leading_hook(piece.content, piece.hook) != piece.content:
        return StyleIssue(
            severity="error",
            issue_type="duplicate_hook",
            location="content opening",
            description="The hook is repeated as the opening paragraph of the article body.",
            suggestion="Start the content at '## The Problem'; the hook is rendered separately.",
        )
    return None
```

- [ ] **Step 2: Wire the hook check into `check_style_compliance`**

In `check_style_compliance`, after the `issues.extend(_check_banned_words(piece.content))` line, add:
```python
    hook_issue = check_repeated_hook(piece)
    if hook_issue:
        issues.append(hook_issue)
```

- [ ] **Step 3: Add the number-dedup + dual-layer rules to the LLM prompt**

In `STYLE_CHECK_PROMPT`, after rule 4 (`Required sections`), add:
```
5. **No repeated headline number** — The same headline metric should not be asserted verbatim in BOTH the signal block AND the structured abstract's key_result. Restating a number in "## The Results" with its baseline is fine (that's where it's explained). Flag only true redundant assertions, severity "warning".

6. **Dual-layer implications** — "## Why It Matters" should serve both a builder (what to try/adopt) and a non-builder decision-maker (cost/risk/capability/timing). If it speaks only to niche-infra builders, flag severity "warning".
```
And add these to the `issue_type` enum in the JSON schema line: `"repeated_number" | "single_audience" |`.

- [ ] **Step 4: Reconcile `tests/test_style.py` to the real API**

Change the import block at the top of `tests/test_style.py` from:
```python
from scipaper.verify.style import (
    StyleConfig,
    check_banned_words,
    check_citations,
    check_structure,
    check_word_count,
    check_style_compliance,
)
```
to:
```python
from scipaper.verify.style import (
    StyleConfig,
    check_banned_words,
    check_word_count,
    check_repeated_hook,
    check_style_compliance,
)
```
Then delete or rewrite any test in the file that calls the removed `check_citations` / `check_structure` (citations and structure are now checked inside `check_style_compliance` via the LLM). For each such test, either remove it or convert it to assert on `check_banned_words` / `check_word_count` behavior. Keep the file's `make_piece` helper.

- [ ] **Step 5: Add tests for the new deterministic checks**

Add to `tests/test_style.py`:
```python
def test_check_repeated_hook_flags_duplicate():
    piece = make_piece(
        hook="Models fail on most tasks.",
        content=(
            "Models fail on most tasks.\n\n"
            "## The Problem\nX [§1].\n\n## What They Did\nY [§2].\n\n"
            "## The Results\nZ [§3].\n\n## Why It Matters\nW [§4]."
        ),
    )
    issue = check_repeated_hook(piece)
    assert issue is not None
    assert issue.severity == "error"
    assert issue.issue_type == "duplicate_hook"


def test_check_repeated_hook_passes_clean():
    piece = make_piece(
        hook="Models fail on most tasks.",
        content=(
            "## The Problem\nX [§1].\n\n## What They Did\nY [§2].\n\n"
            "## The Results\nZ [§3].\n\n## Why It Matters\nW [§4]."
        ),
    )
    assert check_repeated_hook(piece) is None


def test_check_banned_words_still_flags():
    issues = check_banned_words("This is a revolutionary result.")
    assert any(i.issue_type == "banned_word" for i in issues)


def test_check_word_count_reports_ok():
    words, ok = check_word_count("one two three", StyleConfig(min_words=1, max_words=10))
    assert words == 3 and ok is True
```

- [ ] **Step 6: Run the style tests**

Run: `python -m pytest tests/test_style.py -v`
Expected: collection succeeds (import error gone); all tests pass.

- [ ] **Step 7: Commit**

```bash
git add scipaper/verify/style.py tests/test_style.py
git commit -m "feat: deterministic hook-dup style gate; reconcile test_style to current API"
```

---

## Task 6: Edition length budget

**Files:**
- Modify: `scipaper/generate/edition.py`
- Test: `tests/test_edition.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_edition.py` (use the module's existing edition/piece fixtures; construct pieces with the given `word_count`):
```python
def test_check_edition_length_warns_when_over_budget():
    from scipaper.generate.edition import check_edition_length, Edition
    from scipaper.generate.writer import Piece

    def p(wc):
        return Piece(paper_id="x", title="t", hook="h", content="c",
                     word_count=wc, citations=[], generated_at="t", model_used="t")

    over = Edition(week="2026-W29", issue_number=18,
                   pieces=[p(1500), p(1500), p(1500)], quick_takes=[])
    within = Edition(week="2026-W29", issue_number=18,
                     pieces=[p(900), p(900), p(900)], quick_takes=[])

    assert check_edition_length(over) is False      # 4500 > 3000
    assert check_edition_length(within) is True     # 2700 within budget
```
(Match `Edition(...)`/`Piece(...)` constructor args to their real signatures.)

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_edition.py::test_check_edition_length_warns_when_over_budget -v`
Expected: FAIL with `ImportError: cannot import name 'check_edition_length'`

- [ ] **Step 3: Implement**

Add to `scipaper/generate/edition.py`:
```python
EDITION_WORD_BUDGET = 3000


def check_edition_length(edition: "Edition", budget: int = EDITION_WORD_BUDGET) -> bool:
    """
    Return True if the edition's total feature word count is within budget.
    Logs a warning (non-fatal) when over — editions still ship.
    """
    total = sum(p.word_count for p in edition.pieces)
    if total > budget:
        logger.warning(
            f"Edition {edition.week} is {total} words (> {budget} budget); "
            f"tighten the longest pieces."
        )
        return False
    return True
```
(Ensure `logger` exists in `edition.py`; if not, add `import logging` and `logger = logging.getLogger(__name__)`.)

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_edition.py::test_check_edition_length_warns_when_over_budget -v`
Expected: PASS

- [ ] **Step 5: Call it during assembly (non-fatal)**

In `assemble_edition` (in `edition.py`), just before returning the assembled `Edition`, add:
```python
    check_edition_length(edition)
```
(This logs a warning only — it must NOT raise or drop pieces.)

- [ ] **Step 6: Commit**

```bash
git add scipaper/generate/edition.py tests/test_edition.py
git commit -m "feat: warn when an edition exceeds the ~3000-word (12-min) budget"
```

---

## Task 7: Full verification + sample regeneration

- [ ] **Step 1: Run the whole suite**

Run: `python -m pytest tests/ -q`
Expected: all green EXCEPT the one known pre-existing `tests/test_email.py::TestSendEditionEmail::test_sends_to_buttondown_api` failure. If anything else is red, fix it before proceeding.

- [ ] **Step 2: Regenerate a sample piece and eyeball the prose**

Run: `python demo_pipeline.py`
Read the generated piece's output and confirm:
- The hook does NOT appear twice (once as hook, not again as the body's first paragraph).
- The limitations do NOT end with a reflexive "1–2 years out" clause.
- "Why It Matters" does NOT open with "This is a lab proof-of-concept" and speaks to both a builder and a decision-maker.
- No headline number is asserted verbatim in the signal block AND the key_result.

(If `demo_pipeline.py` uses mocked LLM output, update its mock fixture so the sample content starts at `## The Problem` — the demo should model the new contract.)

- [ ] **Step 3: Update the plan checklist + final report**

Report: which tasks landed, the sample-piece before/after, and the two pre-existing red tests left untouched (`test_style` now fixed; `test_sends_to_buttondown_api` still red — out of scope, flag for a separate fix).

---

## Self-review notes (author)

- **Spec coverage:** D3 (audience slip) → Task 1.4 + Task 4.4; D4 (hook dup / repeated number) → Tasks 2, 3, 4.1–4.2, 5.1–5.3; D5 ("1–2 years"/maturity tic) → Tasks 1.2–1.3, 4.3–4.4; D7 (length) → Tasks 1.6, 6. D1 (throughline) and D2 (monoculture) are **Phase 2**, not here. D6 (relevance) is **Phase 3**.
- **Out of scope (tracked separately):** the `archive.html` "1 pieces" counter bug (needs its own investigation of the archive data source — do not fabricate a fix here); the pre-existing `test_sends_to_buttondown_api` failure.
- **Type consistency:** `strip_leading_hook(content, hook)` used identically in text_utils, web.py, email.py, and style.py. `check_repeated_hook(piece)`, `check_banned_words(content)`, `check_word_count(content, config)`, `check_edition_length(edition, budget)` — signatures match their call sites.
- **Assumption to verify at execution time:** the exact `Edition(...)` and `Piece(...)` constructor signatures (kwargs like `quick_takes`) — confirm against `edition.py`/`writer.py` before running the test steps; adjust the fixtures if they differ.
