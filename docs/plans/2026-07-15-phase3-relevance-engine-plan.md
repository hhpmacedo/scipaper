# Phase 3 — Relevance Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Signal's picks *credibly relevant* — so a reader sees why a paper was chosen — by (A) feeding real traction/quality signals into scoring, (B) adopting a rolling coverage window so a paper can be picked once signal accrues (not only the week it's posted), and (C) surfacing a grounded "why this, now" line per piece. Fully autonomous; every new data source is **degradable** (a failure never blocks a publish and never zeroes the whole score).

**Architecture:** Three independently-shippable sub-phases. **3A** implements/upgrades signal sources (deeper Semantic Scholar, Reddit, Hugging Face Papers + GitHub stars, a curated prestige list). **3B** adds a persistent backlog (`data/backlog.json`) and threads a rolling window through `run_pipeline`. **3C** rebalances scoring for the window, generates a deterministic per-piece "why this, now" line from the concrete signals, and adds X/Twitter **last, behind a flag**. Ship 3A → 3B → 3C in order; each is useful alone.

**Tech Stack:** Python 3.14, `httpx` (async), pytest. External calls are mocked in tests (parse path + failure path); the internal logic (scoring, backlog, note templating) is fully TDD'd.

---

## Pre-existing state (baseline)

Run `python -m pytest tests/ -q`. Expected: **248 passed, 1 failed** (`tests/test_email.py::TestSendEditionEmail::test_sends_to_buttondown_api`, pre-existing/out of scope). Phases 1 and 2 are merged on this branch. Requirements installed via `pip install -r requirements.txt`.

Relevant existing code (confirmed):
- `scipaper/curate/models.py` — `Paper` already has `citation_count`, `reference_count`, `twitter_mentions`, `hn_points`, `reddit_score`, `semantic_scholar_id`, `published_date`, `ingested_at`.
- `scipaper/curate/ingest.py` — `SemanticScholarSource.enrich` (pulls citationCount/referenceCount/externalIds); `SocialSignalSource.get_hn_points` (real, HN Algolia), `get_twitter_mentions`/`get_reddit_score` (stubs → 0); `ingest_papers` orchestrates enrichment in `_enrich_one`.
- `scipaper/curate/score.py` — `_citation_velocity`, `_social_signal_score` (reads hn/twitter/reddit), `score_relevance` (weighted), `ScoringConfig` weights, `score_papers_two_pass`.
- `scipaper/pipeline.py` — `run_pipeline`: `ingest_papers` → `score_papers_two_pass` → `select_edition_papers` → generate/verify/assemble/publish. Config dataclass around line 55; `data/` holds `anchors/`, `cache.db`.

**Cross-cutting rule (every task in 3A/3C):** a new source lives behind a try/except that logs and returns a neutral value (0 / None) on ANY failure — network, auth, unexpected JSON. It contributes a *bounded* additive signal; it must never raise into `ingest_papers`/`run_pipeline` and never zero an otherwise-good score.

---

## File structure

| File | Responsibility | Tasks |
|---|---|---|
| `scipaper/curate/models.py` | New `Paper` signal fields; `PRESTIGE` handling | 1,3,4 |
| `scipaper/curate/ingest.py` | Deeper Sem-Scholar; Reddit; HF/GitHub source; wire into `_enrich_one` | 1,2,3,9 |
| `scipaper/curate/score.py` | Consume new signals; `ScoringConfig` weights; rebalance | 1,3,7 |
| `data/prestige.json` | Curated lab/author list (version-controlled) | 4 |
| `scipaper/curate/prestige.py` | Load prestige list; `prestige_score(paper)` | 4 |
| `scipaper/curate/backlog.py` | `Backlog` persistence (`data/backlog.json`) | 5 |
| `scipaper/pipeline.py` | Thread rolling window through `run_pipeline` | 6 |
| `scipaper/curate/relevance_note.py` | Deterministic "why this, now" from signals | 8 |
| renderers + `Piece` | Carry + render the relevance note | 8 |
| `tests/...` | One test file per module above | all |

---

# Sub-phase 3A — Signal sources

## Task 1: Deeper Semantic Scholar enrichment

**Files:** `scipaper/curate/models.py`, `scipaper/curate/ingest.py`, `scipaper/curate/score.py`, `tests/test_ingest.py`, `tests/test_score.py`

- [ ] **Step 1: Failing test (parse + degrade)** — add to `tests/test_ingest.py`:
```python
def test_semantic_scholar_pulls_influential_and_hindex(monkeypatch):
    import httpx
    from scipaper.curate.ingest import SemanticScholarSource
    from scipaper.curate.models import Paper
    from .conftest import run_async

    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"citationCount": 40, "referenceCount": 30,
                    "influentialCitationCount": 7,
                    "externalIds": {"CorpusId": 123},
                    "authors": [{"hIndex": 55}, {"hIndex": 12}]}

    class FakeClient:
        async def get(self, *a, **k): return FakeResp()

    paper = Paper(arxiv_id="2607.00001", title="t", abstract="a")
    out = run_async(SemanticScholarSource().enrich(paper, FakeClient()))
    assert out.citation_count == 40
    assert out.influential_citation_count == 7
    assert out.max_author_h_index == 55


def test_semantic_scholar_degrades_on_error():
    from scipaper.curate.ingest import SemanticScholarSource
    from scipaper.curate.models import Paper
    from .conftest import run_async

    class BoomClient:
        async def get(self, *a, **k): raise RuntimeError("down")

    paper = Paper(arxiv_id="2607.00002", title="t", abstract="a")
    out = run_async(SemanticScholarSource().enrich(paper, BoomClient()))
    assert out.influential_citation_count == 0 and out.max_author_h_index == 0
```

- [ ] **Step 2: Run → fail** (`AttributeError: influential_citation_count`).
Run: `python -m pytest tests/test_ingest.py -k "semantic_scholar" -v`

- [ ] **Step 3: Add fields** to `Paper` in `models.py` (with the other Semantic Scholar fields):
```python
    influential_citation_count: int = 0
    max_author_h_index: int = 0
```

- [ ] **Step 4: Extend `enrich`** — change the fields query to `citationCount,referenceCount,influentialCitationCount,externalIds,authors.hIndex` and after the existing assignments add:
```python
            paper.influential_citation_count = data.get("influentialCitationCount", 0) or 0
            authors = data.get("authors") or []
            h_indices = [a.get("hIndex") or 0 for a in authors]
            paper.max_author_h_index = max(h_indices) if h_indices else 0
```
Keep everything inside the existing try/except so failure leaves the fields at their `0` defaults.

- [ ] **Step 5: Use in scoring** — in `score.py`, extend `_citation_velocity` OR add a small `_quality_signal(paper)` (0-1) combining influential citations + author h-index, and add a weight. Minimal version: in `_social_signal_score` add nothing (that's traction); instead add to `score_relevance` a `quality` term. Add to `ScoringConfig`:
```python
    quality_signal_weight: float = 0.10
```
and reduce `topic_match_weight` to `0.30` so weights still sum sensibly (topic .30 + keyword .20 + institution .15 + citation_velocity .10 + social .15 + quality .10 = 1.00 — adjust citation_velocity_weight to 0.10). Add:
```python
def _quality_signal(paper) -> float:
    """Influential citations + top author h-index, normalized 0-1."""
    infl = min((paper.influential_citation_count or 0) / 10.0, 1.0)
    hidx = min((paper.max_author_h_index or 0) / 60.0, 1.0)
    return max(infl, hidx)
```
Wire it into `score_relevance`'s weighted sum. Add a test in `tests/test_score.py` asserting a paper with high influential citations scores higher than an identical one without.

- [ ] **Step 6: Run** `python -m pytest tests/test_ingest.py tests/test_score.py -q` → green. **Commit:** `feat: deeper Semantic Scholar signals (influential citations, author h-index)`

## Task 2: Reddit r/MachineLearning signal

**Files:** `scipaper/curate/ingest.py`, `tests/test_ingest.py`

Reddit's public search JSON needs no OAuth for read, but requires a descriptive `User-Agent`. Endpoint: `https://www.reddit.com/r/MachineLearning/search.json?q=<arxiv_id>&restrict_sr=1&sort=top`. Degrade on anything unexpected.

- [ ] **Step 1: Failing test** (mock httpx client returning a search payload with `data.children[].data.score`; assert max score returned; and a failure path returning 0). Follow the exact mock style of the existing HN test in `tests/test_ingest.py`.
- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement `get_reddit_score`** replacing the stub — GET the endpoint with `headers={"User-Agent": "signal-newsletter/1.0"}`, parse `data["data"]["children"]`, return `max(child["data"]["score"] ...)` or 0; wrap in try/except returning 0. **Verify the response shape defensively** (`.get` chains); return 0 on any KeyError/TypeError.
- [ ] **Step 4: Wire into `_enrich_one`** in `ingest_papers` (a new semaphore-guarded block mirroring the HN one, setting `paper.reddit_score`).
- [ ] **Step 5: Run tests → green. Commit:** `feat: Reddit r/MachineLearning traction signal (degradable)`

## Task 3: Hugging Face Papers + GitHub stars (community signal)

**Files:** `scipaper/curate/models.py`, `scipaper/curate/ingest.py`, `scipaper/curate/score.py`, `tests/test_ingest.py`

HF Papers exposes per-paper upvotes (e.g. `https://huggingface.co/api/papers/<arxiv_id>` → `{upvotes, ...}`); GitHub stars come from a repo linked in the paper (via Papers with Code `https://paperswithcode.com/api/v1/papers/?arxiv_id=<id>` then the repo, or the arXiv abstract's GitHub URL). These are the most fragile sources — implement defensively, degrade to 0.

- [ ] **Step 1: Add fields** to `Paper`: `hf_upvotes: int = 0`, `github_stars: int = 0`.
- [ ] **Step 2: Failing tests** — a `CommunitySignalSource` with `get_hf_upvotes(paper, client)` and `get_github_stars(paper, client)`; mock success + failure paths (assert 0 on failure).
- [ ] **Step 3: Implement `CommunitySignalSource`** (new class in `ingest.py`) — each method GETs its endpoint, defensively parses, returns an int, degrades to 0 on any error. Keep timeouts short (5s).
- [ ] **Step 4: Wire into `_enrich_one`** (semaphore-guarded), set `paper.hf_upvotes`, `paper.github_stars`.
- [ ] **Step 5: Feed into `_social_signal_score`** in `score.py` — add HF upvotes (notable at ~50) and GitHub stars (notable at ~500) into the `max(...)` of the social score:
```python
    if paper.hf_upvotes > 0:
        score = max(score, min(paper.hf_upvotes / 50.0, 1.0))
    if paper.github_stars > 0:
        score = max(score, min(paper.github_stars / 500.0, 1.0))
```
Add a `tests/test_score.py` assertion.
- [ ] **Step 6: Run → green. Commit:** `feat: Hugging Face upvotes + GitHub stars community signal (degradable)`

## Task 4: Curated lab/author prestige list

**Files:** `data/prestige.json`, `scipaper/curate/prestige.py`, `scipaper/curate/score.py`, `tests/test_prestige.py`, `tests/test_score.py`

- [ ] **Step 1: Create `data/prestige.json`** — a small, version-controlled, easily-editable list:
```json
{
  "labs": ["deepmind", "google research", "openai", "anthropic", "meta ai", "fair",
           "microsoft research", "allen institute", "ai2", "stanford", "mit", "berkeley",
           "cmu", "eth zurich", "tsinghua", "mila"],
  "authors": []
}
```
- [ ] **Step 2: Failing tests** for `scipaper/curate/prestige.py`: `load_prestige(path)` returns the dict; `prestige_score(paper, prestige)` returns `1.0` when an author affiliation matches a lab (substring, case-insensitive), `0.0` otherwise; missing/corrupt file → empty prestige, score `0.0` (degradable).
- [ ] **Step 3: Implement** `load_prestige` (try/except → `{"labs": [], "authors": []}` on any error) and `prestige_score`.
- [ ] **Step 4: Use in scoring** — load prestige once in `score_papers_two_pass`/`ScoringConfig` (pass the loaded dict via config, default loaded from `data/prestige.json`), and add a `prestige_weight: float = 0.05` term to `score_relevance` (re-normalize the weights to sum ~1.0). This complements the anchor doc's `institutions_of_interest` (which is week-specific) with a stable base list.
- [ ] **Step 5: Run → green. Commit:** `feat: curated lab/author prestige signal in relevance scoring`

---

# Sub-phase 3B — Rolling coverage window

## Task 5: Backlog persistence

**Files:** `scipaper/curate/backlog.py`, `tests/test_backlog.py`

A JSON-backed store so papers survive across weekly runs and can be reconsidered as signal accrues.

- [ ] **Step 1: Failing tests** in `tests/test_backlog.py`:
```python
def test_backlog_merge_and_eligible(tmp_path):
    from scipaper.curate.backlog import Backlog
    from scipaper.curate.models import Paper
    from datetime import datetime, timezone, timedelta

    path = tmp_path / "backlog.json"
    bl = Backlog(path)
    now = datetime(2026, 7, 15, tzinfo=timezone.utc)
    fresh = Paper(arxiv_id="a", title="t", abstract="x", published_date=now)
    old = Paper(arxiv_id="b", title="t", abstract="x", published_date=now - timedelta(days=40))
    bl.merge_new([fresh, old], seen_at=now)
    elig_ids = {p.arxiv_id for p in bl.eligible(now=now, within_days=28)}
    assert "a" in elig_ids and "b" not in elig_ids   # old paper aged out


def test_backlog_marks_covered_and_persists(tmp_path):
    from scipaper.curate.backlog import Backlog
    from scipaper.curate.models import Paper
    from datetime import datetime, timezone
    path = tmp_path / "backlog.json"
    now = datetime(2026, 7, 15, tzinfo=timezone.utc)
    Backlog(path).merge_new([Paper(arxiv_id="a", title="t", abstract="x", published_date=now)], seen_at=now)
    bl = Backlog(path)  # reload from disk
    bl.mark_covered(["a"], week="2026-W29")
    assert not any(p.arxiv_id == "a" for p in bl.eligible(now=now, within_days=28))  # covered excluded


def test_backlog_degrades_on_corrupt_file(tmp_path):
    from scipaper.curate.backlog import Backlog
    path = tmp_path / "backlog.json"
    path.write_text("{ not json")
    bl = Backlog(path)                     # must not raise
    assert bl.eligible(within_days=28) == []
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement `Backlog`** — load `data/backlog.json` on construction (corrupt/missing → empty, logged). Store per paper: `arxiv_id`, serialized paper metadata, `first_seen`, `last_seen`, `covered` (bool), `covered_week`. Methods:
  - `merge_new(papers, seen_at)` — insert new, update `last_seen` + refreshed signal fields for existing; `save()`.
  - `eligible(now=None, within_days=28, exclude_covered=True)` — return `Paper` objects whose `published_date` (or `first_seen`) is within the window and not covered.
  - `mark_covered(ids, week)` — set covered flag; `save()`.
  - `save()` — atomic write to the JSON path.
  Use `published_date` for the age test; fall back to `first_seen` when `published_date` is missing. Dates serialize via ISO strings.
- [ ] **Step 4: Run → green. Commit:** `feat: persistent paper backlog for rolling coverage window`

## Task 6: Thread the rolling window through the pipeline

**Files:** `scipaper/pipeline.py`, `tests/test_pipeline.py`

- [ ] **Step 1: Failing test** — a `run_pipeline` test (mock ingest to return a couple of papers, mock scoring/generation as the existing pipeline tests do) asserting that: (a) ingested papers are merged into a backlog at `config`'s backlog path (point it at `tmp_path`), and (b) after a run, the selected papers are marked covered in the backlog. Mirror the mocking already in `tests/test_pipeline.py`.
- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** — add to the pipeline config dataclass:
```python
    backlog_path: Path = Path("data/backlog.json")
    rolling_window_days: int = 28
    use_rolling_window: bool = True
```
In `run_pipeline`, after `papers = await ingest_papers(...)`:
```python
    pool = papers
    backlog = None
    if config.use_rolling_window:
        try:
            from .curate.backlog import Backlog
            backlog = Backlog(config.backlog_path)
            backlog.merge_new(papers, seen_at=datetime.now(timezone.utc))
            pool = backlog.eligible(within_days=config.rolling_window_days)
            logger.info(f"Rolling window: {len(pool)} eligible papers ({len(papers)} fresh)")
        except Exception as e:
            logger.warning(f"Backlog unavailable ({e}); using fresh papers only")
            pool = papers
```
Score/select on `pool` instead of `papers`. After selection, before/after generation:
```python
    if backlog is not None:
        try:
            backlog.mark_covered([sp.paper.arxiv_id for sp in selected], week=anchor.week)
        except Exception as e:
            logger.warning(f"Failed to mark covered: {e}")
```
Degradability: any backlog failure falls back to fresh-only; a publish is never blocked.
- [ ] **Step 4: Run → green. Commit:** `feat: rolling coverage window — score/select over the eligible backlog`

---

# Sub-phase 3C — Surfacing, rebalance, and X/Twitter

## Task 7: Rebalance scoring for the window

**Files:** `scipaper/curate/score.py`, `tests/test_score.py`

With a rolling window, fast traction signals are meaningful (they accrue over weeks). Confirm the `ScoringConfig` weights (after Tasks 1/3/4) sum to ~1.0, and add a mild **recency-decay** so a paper doesn't stay top-ranked for a month on freshness alone.

- [ ] **Step 1: Failing test** — two identical papers except `published_date` (one 2 days old, one 25 days old) with equal signals: the fresher one scores `>=` the older; but an older paper with strong traction (high citations/upvotes) can outrank a fresh one with none. Encode both assertions.
- [ ] **Step 2: Implement** a `_recency_factor(paper, now, half_life_days=14)` (multiplicative, in [0.6, 1.0]) applied to the freshness-derived part of relevance only (do NOT decay the traction/quality signals — those are the whole point of the window). Add `recency_half_life_days` to `ScoringConfig`. Keep the 1–10 scaling.
- [ ] **Step 3: Run → green. Commit:** `feat: recency-aware scoring balanced against accrued traction`

## Task 8: Per-piece "why this, now" line

**Files:** `scipaper/curate/relevance_note.py`, `scipaper/generate/writer.py` (or `ScoredPaper`→`Piece` flow), renderers, tests

A short, grounded, **deterministic** line built from the actual signals — no LLM (cheaper, always grounded). Example: "Gaining traction: 120 HF upvotes, 8 early citations, from a top lab."

- [ ] **Step 1: Failing tests** in `tests/test_relevance_note.py`:
```python
def test_relevance_note_summarizes_strongest_signals():
    from scipaper.curate.relevance_note import relevance_note
    from scipaper.curate.models import Paper
    p = Paper(arxiv_id="a", title="t", abstract="x",
              hf_upvotes=120, citation_count=8, hn_points=0)
    note = relevance_note(p)
    assert "120" in note and ("upvote" in note.lower() or "HF" in note)


def test_relevance_note_empty_when_no_signal():
    from scipaper.curate.relevance_note import relevance_note
    from scipaper.curate.models import Paper
    assert relevance_note(Paper(arxiv_id="a", title="t", abstract="x")) == ""
```
- [ ] **Step 2: Implement `relevance_note(paper) -> str`** — pick the 1–3 strongest signals (HF upvotes, HN points, influential/early citations, GitHub stars, prestige-lab membership) above per-signal thresholds and format a short human phrase; return `""` when nothing clears threshold (so the renderer shows nothing).
- [ ] **Step 3: Carry onto the piece** — add `Piece.relevance_note: Optional[str] = None`; set it during generation from the paper (the pipeline has the `ScoredPaper`/`Paper` when it builds each `Piece`). Do NOT block generation on it.
- [ ] **Step 4: Render** — show the note as a small labeled line under the piece's structured abstract in `web.py` and `email.py` (HTML + plain text), only when non-empty. Add render tests (present → shown; empty/None → absent).
- [ ] **Step 5: Run → green. Commit:** `feat: grounded per-piece "why this, now" relevance line`

## Task 9: X/Twitter signal — behind a flag, wired last

**Files:** `scipaper/curate/ingest.py`, `tests/test_ingest.py`

- [ ] **Step 1: Failing tests** — `get_twitter_mentions(paper, client)` returns a count when `enable_twitter=True` and a bearer token is configured (mock the API response), and returns `0` (no call) when the flag is off or no token. A failure path returns 0.
- [ ] **Step 2: Implement** — add `enable_twitter: bool = False` to `IngestConfig` and read a bearer token from config/env. `get_twitter_mentions` short-circuits to `0` unless flag AND token are present; otherwise queries the API (recent search count for the arXiv id/URL), defensively parses, degrades to 0. Wire into `_enrich_one` guarded by the flag so a run with the flag off makes NO Twitter calls.
- [ ] **Step 3: Run → green. Commit:** `feat: optional X/Twitter discourse signal (flagged off by default, degradable)`

---

## Task 10: Full verification + review

- [ ] **Step 1:** `python -m pytest tests/ -q` — green except the known `test_sends_to_buttondown_api`.
- [ ] **Step 2:** Confirm degradability end-to-end: with NO network/keys, `ingest_papers` and `run_pipeline` still complete (every new source returns 0/None; backlog falls back). Write/keep a test that runs the pipeline with all external sources mocked to raise, asserting an edition still assembles.
- [ ] **Step 3:** Dispatch a final reviewer over the whole Phase 3 diff (base = Phase 2 HEAD) for spec compliance + code quality, with special attention to: every external source is degradable (never raises into ingest/pipeline, never zeroes a whole score); the backlog window math (age-out, covered-exclusion, corrupt-file fallback); weights still sum ~1.0; X/Twitter makes no calls when the flag is off; the relevance note is grounded and empty when there's no signal.

---

## Self-review notes (author)

- **Spec coverage:** rolling window → Tasks 5–6; free/community sources → Tasks 2,3; deeper Semantic Scholar → Task 1; prestige list → Task 4; X/Twitter (flagged, last) → Task 9; per-piece "why this, now" → Task 8; scoring rebalance → Tasks 1,3,4,7.
- **Degradability (the autonomy guarantee):** every new source is behind try/except → neutral value; the backlog falls back to fresh-only; Task 10 Step 2 proves the whole pipeline still ships with all sources failing. This is the single most important property to preserve in review.
- **Testing reality:** external APIs are mocked (parse path + failure path) — we do NOT hit live services in tests. The deterministic logic (scoring math, backlog window, note templating) is fully TDD'd. A real end-to-end relevance check needs a live run with keys.
- **Assumptions to verify at execution:** exact JSON shapes of Semantic Scholar `authors.hIndex`, HF Papers `/api/papers/<id>`, Papers with Code, Reddit search, and the Twitter recent-search endpoint — implement each defensively and degrade on any mismatch rather than trusting the shape. Confirm the `ScoringConfig` weights re-normalize to ~1.0 after Tasks 1/3/4/7 (do the arithmetic in one place and assert it in a test).
- **Sub-phase independence:** 3A improves relevance even without the window; 3B works with today's signals; 3C surfaces and refines. Ship in order; each is independently reviewable and shippable. X/Twitter is deliberately last and off by default.
- **Weight bookkeeping:** Tasks 1, 3, 4, 7 all touch `ScoringConfig` weights. Add a single test `test_scoring_weights_sum_to_one` early and keep it green through each task to avoid silent drift.
