# Phase 2 — Breadth + Editorial Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the two structural reader complaints — topic monoculture and "a stack of summaries with no point of view" — by (a) broadening what the pipeline ingests, (b) forcing each edition to span multiple distinct research areas, and (c) generating a real "Editor's Note" throughline that replaces the disconnected top-of-issue bullets. Fully autonomous; the Editor's Note is machine-generated and degradable.

**Architecture:** Four tasks. (1) Expand `PaperCategory` so non-LLM fields can surface at all. (2) Map arXiv categories to coarse *areas* and add a "span ≥N areas" rule to selection — Tasks 1 and 2 are complementary (breadth needs both a broad pool and a diversity rule). (3) A new autonomous LLM stage that writes a 60–100-word Editor's Note over the selected pieces, stored on `Edition`, degradable (falls back to the existing bullets on failure). (4) Render the Editor's Note as the lead, most-accessible text.

**Tech Stack:** Python 3.14, pytest, dataclasses. LLM calls follow the existing `generate_quick_take` / `_llm_quick_take` pattern in `scipaper/generate/edition.py` (Anthropic client, model from `get_config()`).

---

## Pre-existing state (baseline)

Run `python -m pytest tests/ -q`. Expected: **234 passed, 1 failed**. The one failure — `tests/test_email.py::TestSendEditionEmail::test_sends_to_buttondown_api` — is pre-existing and out of scope. Any OTHER failure means Phase 1 or the environment is broken; fix before starting. Requirements: `pip install -r requirements.txt`.

Phase 1 is merged on this branch (Style Constitution v1.2.0, hook dedup, de-templatized prompts, style gate, edition length budget).

## File structure

| File | Responsibility | Task |
|---|---|---|
| `scipaper/curate/models.py` | Add categories to `PaperCategory`; add `CATEGORY_AREAS` map + `primary_area(paper)` helper | 1, 2 |
| `scipaper/curate/select.py` | Area-based diversity (`_get_topics` → areas) + `min_distinct_areas` post-pass | 2 |
| `scipaper/generate/edition.py` | `Edition.editor_note` field; `EDITOR_NOTE_PROMPT`; `generate_editor_note` (degradable); call in `assemble_edition` | 3 |
| `scipaper/publish/web.py` | Render Editor's Note as lead; keep bullets as fallback | 4 |
| `scipaper/publish/email.py` | Render Editor's Note (HTML + plain text); fallback | 4 |
| `tests/test_ingest.py` / `tests/test_score.py` | Category set test | 1 |
| `tests/test_select.py` | Area diversity + span tests | 2 |
| `tests/test_edition.py` | Editor's Note generation + degradability tests | 3 |
| `tests/test_web.py`, `tests/test_email.py` | Editor's Note render + fallback tests | 4 |

---

## Task 1: Broaden ingestion categories

**Files:**
- Modify: `scipaper/curate/models.py` (`PaperCategory`)
- Test: `tests/test_ingest.py`

Context: `IngestConfig.categories` defaults to `[c.value for c in PaperCategory]` and `_build_query` ORs `cat:X`. Today the enum is only `cs.AI, cs.LG, cs.CL, stat.ML` — nothing else can ever be ingested. Broaden to cover the field for this audience.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ingest.py`:
```python
def test_ingest_config_covers_broadened_fields():
    from scipaper.curate.ingest import IngestConfig
    cfg = IngestConfig()
    cats = set(cfg.categories)
    # Core (unchanged)
    assert {"cs.AI", "cs.LG", "cs.CL", "stat.ML"} <= cats
    # Broadened fields must now be present
    for c in ["cs.CV", "cs.RO", "cs.MA", "cs.HC", "cs.CY", "cs.SE", "cs.CR", "eess.AS"]:
        assert c in cats, f"missing broadened category {c}"


def test_build_query_includes_broadened_categories():
    from scipaper.curate.ingest import IngestConfig, ArxivSource
    q = ArxivSource(IngestConfig())._build_query()
    assert "cat:cs.RO" in q and "cat:cs.CV" in q and "cat:cs.CL" in q
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_ingest.py -k "broadened" -v`
Expected: FAIL (missing categories).

- [ ] **Step 3: Implement**

In `scipaper/curate/models.py`, replace the `PaperCategory` enum body with:
```python
class PaperCategory(str, Enum):
    """ArXiv categories we track. Broadened (Phase 2) to span the field, not just LLM/ML."""
    CS_AI = "cs.AI"      # AI / agents / reasoning
    CS_LG = "cs.LG"      # machine learning methods
    CS_CL = "cs.CL"      # NLP / language
    STAT_ML = "stat.ML"  # statistical ML
    CS_CV = "cs.CV"      # computer vision
    CS_RO = "cs.RO"      # robotics
    CS_MA = "cs.MA"      # multi-agent systems
    CS_HC = "cs.HC"      # human-computer interaction
    CS_CY = "cs.CY"      # computers & society (policy, economics, ethics)
    CS_SE = "cs.SE"      # software engineering
    CS_CR = "cs.CR"      # security & cryptography
    EESS_AS = "eess.AS"  # audio & speech
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_ingest.py -k "broadened" -v`
Expected: PASS. Then `python -m pytest tests/test_ingest.py tests/test_score.py -q` — expected green (if a test hard-coded the old 4-category list, update it to assert the core four are a subset, not the whole set).

- [ ] **Step 5: Commit**

```bash
git add scipaper/curate/models.py tests/test_ingest.py
git commit -m "feat: broaden ingested arXiv categories across the AI field"
```

---

## Task 2: Area-based diversity + span-≥N-areas rule

**Files:**
- Modify: `scipaper/curate/models.py` (add `CATEGORY_AREAS`, `primary_area`)
- Modify: `scipaper/curate/select.py`
- Test: `tests/test_select.py`

Context: `select.py::_get_topics` returns `set(paper.categories)` — the raw arXiv tags. Because cs.AI/cs.LG sit on nearly every paper, `max_same_topic=2` barely bites. Fix: map each paper to ONE coarse area (via its primary category) and (a) cap papers per area, (b) require the edition to span at least `min_distinct_areas`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_select.py` (reuse the module's existing `ScoredPaper`/`Paper` construction helpers; if none, build a `ScoredPaper` the way other tests in the file do — inspect first):
```python
def test_primary_area_maps_categories():
    from scipaper.curate.models import primary_area, Paper
    assert primary_area(Paper(arxiv_id="1", title="", abstract="", categories=["cs.RO", "cs.AI"])) == "robotics"
    assert primary_area(Paper(arxiv_id="2", title="", abstract="", categories=["cs.CL"])) == "nlp"
    assert primary_area(Paper(arxiv_id="3", title="", abstract="", categories=["cs.LG"])) == "ml-methods"
    assert primary_area(Paper(arxiv_id="4", title="", abstract="", categories=[])) == "other"


def test_selection_spans_min_distinct_areas():
    from scipaper.curate.select import select_edition_papers, SelectionConfig
    # 6 high-scoring agent papers + 1 robotics + 1 vision, all eligible.
    # Without the span rule, greedy picks agent papers only; with it, robotics+vision surface.
    papers = (
        [_mk(f"a{i}", ["cs.AI"], score=9.0) for i in range(6)]
        + [_mk("r1", ["cs.RO"], score=6.0), _mk("v1", ["cs.CV"], score=6.0)]
    )
    selected = select_edition_papers(papers, SelectionConfig(target_count=5, min_distinct_areas=3, max_same_topic=2))
    from scipaper.curate.models import primary_area
    areas = {primary_area(p.paper) for p in selected}
    assert len(areas) >= 3
    assert "robotics" in areas and "vision" in areas
```
Add a `_mk` helper near the top of the test (adapt field names to the real `Paper`/`ScoredPaper` signatures — set `relevance_score`, `narrative_potential_score`, and `composite_score` so the paper is eligible and ordered by score):
```python
def _mk(pid, cats, score):
    from scipaper.curate.models import Paper, ScoredPaper
    paper = Paper(arxiv_id=pid, title=f"t{pid}", abstract="a", categories=cats)
    sp = ScoredPaper(paper=paper)
    sp.relevance_score = score
    sp.narrative_potential_score = score
    sp.composite_score = score
    return sp
```
(If `ScoredPaper`/`select_edition_papers` read scores from different attributes, match them — read `scipaper/curate/models.py` and `select.py` first. `select_edition_papers` expects `eligible` sorted by score; if it does not sort internally, pass the list already sorted high→low.)

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_select.py -k "primary_area or spans_min" -v`
Expected: FAIL (`primary_area` undefined; `min_distinct_areas` not a `SelectionConfig` field; span not enforced).

- [ ] **Step 3: Add the area map + helper**

In `scipaper/curate/models.py`, after the `PaperCategory` enum, add:
```python
# Coarse research areas for edition diversity. Maps arXiv category -> area label.
CATEGORY_AREAS = {
    "cs.CL": "nlp",
    "cs.CV": "vision",
    "eess.IV": "vision",
    "cs.RO": "robotics",
    "cs.AI": "agents",
    "cs.MA": "agents",
    "cs.LG": "ml-methods",
    "stat.ML": "ml-methods",
    "cs.HC": "hci",
    "cs.CY": "society",
    "cs.SE": "software",
    "cs.CR": "security",
    "eess.AS": "speech",
}


def primary_area(paper: "Paper") -> str:
    """
    Map a paper to ONE coarse research area via its primary (first) arXiv
    category. Falls back to scanning all categories, then "other".
    """
    cats = paper.categories or []
    if cats and cats[0] in CATEGORY_AREAS:
        return CATEGORY_AREAS[cats[0]]
    for c in cats:
        if c in CATEGORY_AREAS:
            return CATEGORY_AREAS[c]
    return "other"
```

- [ ] **Step 4: Use areas in selection + add the span post-pass**

In `scipaper/curate/select.py`:

(a) Add the import at the top:
```python
from .models import Paper, ScoredPaper, primary_area
```

(b) Add a field to `SelectionConfig`:
```python
    min_distinct_areas: int = 3   # every edition must span at least this many areas
```

(c) Replace `_get_topics` with area-based logic:
```python
def _get_topics(paper: Paper) -> Set[str]:
    """A paper's coarse research area (single-element set) for diversity capping."""
    return {primary_area(paper)}
```

(d) After the greedy-selection loop and BEFORE the "relax constraints to meet minimum" block, add a span-enforcement pass:
```python
    # Ensure the edition spans at least min_distinct_areas areas. If not, swap the
    # lowest-scoring selected paper from an over-represented area for the highest-
    # scoring eligible paper from a missing area.
    def _areas(papers):
        return Counter(primary_area(p.paper) for p in papers)

    while len({primary_area(p.paper) for p in selected}) < config.min_distinct_areas:
        present = {primary_area(p.paper) for p in selected}
        candidate = next(
            (p for p in eligible
             if p not in selected and primary_area(p.paper) not in present),
            None,
        )
        if candidate is None:
            logger.info("Cannot reach min_distinct_areas; not enough area diversity in pool")
            break
        area_counts = _areas(selected)
        # Drop the lowest-scoring selected paper whose area appears more than once.
        droppable = sorted(
            (p for p in selected if area_counts[primary_area(p.paper)] > 1),
            key=lambda p: p.composite_score,
        )
        if not droppable:
            # No room to swap without going below area caps; append if under max.
            if len(selected) < config.max_count:
                candidate.selected_for_edition = True
                candidate.selection_reason = "Added for area diversity"
                selected.append(candidate)
                continue
            break
        drop = droppable[0]
        drop.selected_for_edition = False
        selected.remove(drop)
        candidate.selected_for_edition = True
        candidate.selection_reason = "Swapped in for area diversity"
        selected.append(candidate)
```
(`composite_score` is the ordering key — confirm the attribute name on `ScoredPaper`; if it is `None` for some papers in tests, fall back to `p.composite_score or 0`.)

- [ ] **Step 5: Run to verify they pass**

Run: `python -m pytest tests/test_select.py -v`
Expected: PASS, including existing selection tests (if an existing test asserted the old raw-category diversity behavior, update it to the area semantics).

- [ ] **Step 6: Commit**

```bash
git add scipaper/curate/models.py scipaper/curate/select.py tests/test_select.py
git commit -m "feat: area-based diversity; every edition spans >=3 research areas"
```

---

## Task 3: Editor's Note generation stage (degradable)

**Files:**
- Modify: `scipaper/generate/edition.py`
- Test: `tests/test_edition.py`

Context: The top-of-issue "This week in Signal" is currently just each piece's signal-block first sentence concatenated (built in the renderers) — disconnected and dense. Add an autonomous stage that writes a genuine 60–100-word connective note. It MUST be degradable: any failure leaves `editor_note = None` and the edition still assembles (the renderers fall back to bullets).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_edition.py` (mock the Anthropic client the way `tests/test_style.py` / `tests/test_checker.py` do — inspect the pattern first):
```python
class TestEditorNote:
    def _pieces(self):
        from scipaper.generate.writer import Piece
        def mk(pid, hook):
            return Piece(paper_id=pid, title=f"t{pid}", hook=hook, content="c",
                         word_count=800, citations=[], generated_at="t", model_used="t",
                         signal_block=f"{hook} It is emerging. It informs a decision.")
        return [mk("1", "Routing cuts cost."), mk("2", "Agents fail on noise.")]

    def test_generate_editor_note_returns_text(self):
        import scipaper.generate.edition as ed
        from unittest.mock import patch, MagicMock
        from .conftest import run_async

        fake = MagicMock()
        fake.messages.create.return_value = MagicMock(
            content=[MagicMock(text="This week, two threads converge on agent reliability.")]
        )
        with patch.object(ed, "anthropic", MagicMock(Anthropic=MagicMock(return_value=fake))):
            note = run_async(ed.generate_editor_note(self._pieces(), ed.AssemblyConfig()))
        assert note and "agent reliability" in note

    def test_generate_editor_note_degrades_on_failure(self):
        import scipaper.generate.edition as ed
        from unittest.mock import patch, MagicMock
        from .conftest import run_async

        boom = MagicMock()
        boom.messages.create.side_effect = RuntimeError("api down")
        with patch.object(ed, "anthropic", MagicMock(Anthropic=MagicMock(return_value=boom))):
            note = run_async(ed.generate_editor_note(self._pieces(), ed.AssemblyConfig()))
        assert note is None  # degrades, does not raise
```
(Adapt the mock to however `edition.py` currently constructs its Anthropic client in `_llm_quick_take` — match that exact call surface so the patch lands. If `edition.py` imports `anthropic` lazily inside the function, patch `anthropic.Anthropic` at the module the function imports from.)

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_edition.py -k EditorNote -v`
Expected: FAIL (`generate_editor_note` undefined).

- [ ] **Step 3: Add the `editor_note` field**

In `scipaper/generate/edition.py`, add to the `Edition` dataclass (with the other optional fields):
```python
    # Machine-generated connective throughline shown at the top of the edition.
    editor_note: Optional[str] = None
```

- [ ] **Step 4: Add the prompt + generator**

In `scipaper/generate/edition.py`, add near `QUICK_TAKE_PROMPT`:
```python
EDITOR_NOTE_PROMPT = """You are the editor of Signal, a weekly newsletter that explains AI research to software engineers and PMs who use AI daily but don't read papers.

Write a 60-100 word "Editor's Note" that opens this week's edition. It must:
- Find the genuine throughline across the pieces below (a shared tension, a theme, or a useful contrast) — do NOT just list them.
- Be the MOST accessible text in the issue: plain language, no jargon, no piece titles dumped in a row.
- Have a point of view — what this week means for someone building with or deciding on AI.
- Zero hype. No "revolutionary", "breakthrough", "game-changing". State things plainly.
- End with one sentence orienting the reader ("If you read one thing this week...").

This week's pieces (hook — signal block):
{pieces_block}

Return ONLY the note text, no preamble, no heading."""


async def generate_editor_note(pieces, config=None):
    """
    Generate the edition's Editor's Note throughline. Degradable: returns None
    on any failure (missing pieces, API error) so the edition still ships and
    the renderers fall back to per-piece bullets.
    """
    config = config or AssemblyConfig()
    if not pieces:
        return None
    pieces_block = "\n".join(
        f"- {p.hook} — {(p.signal_block or '').strip()}" for p in pieces
    )
    prompt = EDITOR_NOTE_PROMPT.format(pieces_block=pieces_block)
    try:
        signal_config = get_config()
        client = anthropic.Anthropic(api_key=signal_config.anthropic_api_key)
        response = client.messages.create(
            model=signal_config.llm_model,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        return text or None
    except Exception as e:
        logger.warning(f"Editor's Note generation failed ({e}); edition ships without it")
        return None
```
Ensure `edition.py` imports `anthropic` and `get_config` the same way `_llm_quick_take` / other stages do (check the top of the file; add imports only if the existing quick-take path uses a different mechanism, in which case mirror THAT mechanism exactly).

- [ ] **Step 5: Call it in `assemble_edition`**

In `assemble_edition`, after the `Edition(...)` object is built (or set the field on it) and before the `check_edition_length(edition)` call, add:
```python
    edition.editor_note = await generate_editor_note(edition.pieces, config)
```
(If `assemble_edition` constructs and returns `edition` in one place, set `editor_note` right after construction. It must run on the assembled pieces and must never raise.)

- [ ] **Step 6: Run to verify they pass**

Run: `python -m pytest tests/test_edition.py -k EditorNote -v` then `python -m pytest tests/test_edition.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add scipaper/generate/edition.py tests/test_edition.py
git commit -m "feat: autonomous, degradable Editor's Note throughline on each edition"
```

---

## Task 4: Render the Editor's Note

**Files:**
- Modify: `scipaper/publish/web.py`
- Modify: `scipaper/publish/email.py`
- Test: `tests/test_web.py`, `tests/test_email.py`

Context: In `web.py` the "This week in Signal" block (`issue_summary_html`) is built from per-piece signal-block sentences. Lead with the Editor's Note when present; keep the bullets as a fallback / secondary "In this issue" list.

- [ ] **Step 1: Write the failing test (web)**

Add to `tests/test_web.py`:
```python
def test_editor_note_rendered_as_lead():
    from scipaper.publish.web import generate_edition_page, WebConfig
    from scipaper.generate.writer import Piece
    from scipaper.generate.edition import Edition
    piece = Piece(paper_id="1", title="A Title For The Piece Here", hook="Hook one.",
                  content="## The Problem\nX [§1].\n\n## Why It Matters\nY [§2].",
                  word_count=50, citations=[], generated_at="t", model_used="t",
                  signal_block="Hook one. It is emerging. It informs a decision.")
    ed = Edition(week="2026-W29", issue_number=18, pieces=[piece], quick_takes=[],
                 editor_note="This week, one clear throughline about agents.")
    html = generate_edition_page(ed, WebConfig())
    assert "This week, one clear throughline about agents." in html


def test_falls_back_to_bullets_without_editor_note():
    from scipaper.publish.web import generate_edition_page, WebConfig
    from scipaper.generate.writer import Piece
    from scipaper.generate.edition import Edition
    piece = Piece(paper_id="1", title="A Title For The Piece Here", hook="Hook one.",
                  content="## The Problem\nX [§1].", word_count=50, citations=[],
                  generated_at="t", model_used="t",
                  signal_block="Hook one. It is emerging. It informs a decision.")
    ed = Edition(week="2026-W29", issue_number=18, pieces=[piece], quick_takes=[])  # no note
    html = generate_edition_page(ed, WebConfig())
    assert "This week in Signal" in html  # bullets fallback still present
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_web.py -k "editor_note or fallback" -v`
Expected: `test_editor_note_rendered_as_lead` FAILS (note not rendered); the fallback test should pass already.

- [ ] **Step 3: Implement (web)**

In `scipaper/publish/web.py`, where `issue_summary_html` is built (the `## This week in Signal` block around line 280), wrap it so the Editor's Note leads and the bullets become a fallback/secondary. Replace the block that sets `issue_summary_html` with:
```python
    issue_summary_html = ""
    if getattr(edition, "editor_note", None) and edition.editor_note.strip():
        issue_summary_html = (
            f'<div class="editor-note">'
            f'<p class="editor-note-label">This week in Signal</p>'
            f'<p class="editor-note-body">{escape(edition.editor_note.strip())}</p>'
            f'</div>'
        )
    else:
        summary_lines = []
        for piece in edition.pieces:
            if piece.signal_block and piece.signal_block.strip():
                first_sentence = piece.signal_block.strip().split(". ")[0]
                if not first_sentence.endswith("."):
                    first_sentence += "."
                summary_lines.append(f'<li>{escape(first_sentence)}</li>')
            elif piece.hook:
                summary_lines.append(f'<li>{escape(piece.hook)}</li>')
        if summary_lines:
            issue_summary_html = (
                f'<div class="issue-summary">'
                f'<p class="issue-summary-label">This week in Signal</p>'
                f'<ul>{"".join(summary_lines)}</ul>'
                f'</div>'
            )
```
Add a minimal style rule near the other `.issue-summary` CSS:
```python
.editor-note {{ margin: 0 0 28px; }}
.editor-note-label {{ font-family: "Helvetica Neue", Arial, sans-serif; font-weight: 900; text-transform: uppercase; font-size: 13px; letter-spacing: 0.04em; color: #666; margin-bottom: 6px; }}
.editor-note-body {{ font-size: 18px; line-height: 1.5; }}
```
(Match the f-string escaping style already used in that CSS block — the file doubles braces `{{ }}` inside an f-string; follow the surrounding convention exactly.)

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_web.py -k "editor_note or fallback" -v`
Expected: PASS.

- [ ] **Step 5: Implement + test (email)**

Add an equivalent test to `tests/test_email.py` (`test_editor_note_in_email_html`) asserting `render_edition_html(edition)` contains the editor_note text when present. Then in `scipaper/publish/email.py`, render `edition.editor_note` as a lead paragraph in BOTH `render_edition_html` and `render_edition_text` (plain text: print the note, a blank line, then the pieces). Where the email currently emits its top-of-issue summary/intro, lead with the note when present and fall back to existing behavior otherwise. Confirm the test fails before, passes after.

- [ ] **Step 6: Run the render suites**

Run: `python -m pytest tests/test_web.py tests/test_email.py -q`
Expected: all pass except the known pre-existing `test_sends_to_buttondown_api`.

- [ ] **Step 7: Commit**

```bash
git add scipaper/publish/web.py scipaper/publish/email.py tests/test_web.py tests/test_email.py
git commit -m "feat: render Editor's Note as the lead, bullets as fallback (web + email)"
```

---

## Task 5: Full verification + review

- [ ] **Step 1: Full suite**

Run: `python -m pytest tests/ -q`
Expected: green except the one known pre-existing `test_sends_to_buttondown_api`. Fix anything else.

- [ ] **Step 2: Sanity-check breadth + note wiring**

In a Python REPL or a scratch script (do not commit), construct a small list of `ScoredPaper` across 4 areas and confirm `select_edition_papers` returns ≥3 areas; construct an `Edition` with `editor_note` set and confirm `generate_edition_page` leads with it. (The demo pipeline is stale/mocked; do not rely on it. A real breadth/throughline check needs a live ingestion + generation run with API keys.)

- [ ] **Step 3: Final review**

Dispatch a final reviewer over the whole Phase 2 diff (base = Phase 1 HEAD → current HEAD) for spec compliance + code quality, per subagent-driven-development. Confirm: broadened categories present; area diversity actually forces span; Editor's Note is degradable (never blocks a publish); renderers fall back cleanly when the note is absent.

---

## Self-review notes (author)

- **Spec coverage:** D2 (monoculture) → Tasks 1 + 2 (both required — a broad pool AND a span rule). D1 (no throughline) → Tasks 3 + 4.
- **Degradability (autonomy):** `generate_editor_note` returns `None` on any failure and is set with no `try` around a raising path in `assemble_edition`; renderers treat a missing note as the fallback case. No new hard dependency on a publish.
- **Assumptions to verify at execution:** exact `ScoredPaper` score attribute names and whether `select_edition_papers` sorts `eligible` internally (Task 2 tests depend on score ordering); the exact Anthropic client construction in `edition.py`'s existing quick-take path (Task 3 mock must match it); the email intro/summary location (Task 4).
- **Out of scope (Phase 3):** rolling coverage window, the relevance signal stack (HF Papers, Semantic Scholar velocity, prestige list, X/Twitter), and surfacing a per-piece "why this, now" line.
- **Known limitation:** `primary_area` uses the primary arXiv category; LLM-agent papers frequently carry `cs.AI`/`cs.LG` primaries, so area mapping is coarse. Broadened ingestion (Task 1) is what actually puts robotics/vision/speech papers in the pool; the span rule (Task 2) only helps if such papers clear the score thresholds. If editions still skew LLM-heavy after this, revisit thresholds or add a per-area score bonus in Phase 3.
