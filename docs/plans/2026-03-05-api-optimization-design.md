# API Architecture Optimization — Design Doc

**Date:** 2026-03-05
**Status:** Approved
**Approach:** B ("Smart Pipeline") — Reorder + batch + cache

## Problem

The pipeline makes ~230 LLM calls per run (200 for scoring papers that won't be selected), creates a new HTTP/Anthropic client per API call, runs all enrichment sequentially, has no caching, and no rate limiting. A single run is slow (~10 min), expensive, and fragile under load.

## Goals

1. **Cost:** Cut LLM calls from ~230 to ~35 per run
2. **Speed:** Reduce pipeline runtime from ~10 min to ~2 min
3. **Reliability:** Rate limiting, retry on 429/503, graceful degradation

## Design

### 1. Shared API Clients (`scipaper/clients.py`)

`ClientPool` async context manager holding:

- `httpx.AsyncClient` — shared across all HTTP calls (connection pooling)
- `anthropic.AsyncAnthropic` — single instance for all LLM calls

Lifecycle managed by `pipeline.py`:

```python
async with ClientPool(config) as clients:
    result = await run_pipeline(anchor, config, clients=clients)
```

All module functions (`_score_with_anthropic`, `_generate_with_anthropic`, `_verify_with_anthropic`, `SemanticScholarSource.enrich`, etc.) accept the client as a parameter instead of creating their own.

### 2. Two-Pass Scoring

Current flow (all 200 papers):

```
for paper in papers:
    relevance = score_relevance(paper)      # pure Python
    narrative = score_narrative_potential(paper)  # LLM call
    composite = combine(relevance, narrative)
```

New flow:

```
# Pass 1: fast relevance filter (no LLM)
for paper in papers:
    relevance = score_relevance(paper)

top_candidates = papers sorted by relevance, take top 20

# Pass 2: LLM narrative scoring (concurrent, semaphore=5)
for paper in top_candidates:
    narrative = score_narrative_potential(paper)  # LLM call
    composite = combine(relevance, narrative)
```

New function: `score_papers_two_pass(papers, anchor, config, client)` in `score.py`.

Configuration: `ScoringConfig.relevance_cutoff_count: int = 20` controls how many papers proceed to Pass 2.

### 3. Concurrent Enrichment with Rate Limiting

In `ingest.py`, replace sequential for-loops with `asyncio.gather`:

```python
sem_scholar = asyncio.Semaphore(10)  # ~100 req/5min budget
sem_hn = asyncio.Semaphore(5)

async def _enrich_one(paper, client, sem):
    async with sem:
        return await semantic.enrich(paper, client)

enriched = await asyncio.gather(*[_enrich_one(p, client, sem_scholar) for p in papers])
```

Same pattern for HN lookups and PDF downloads.

`SemanticScholarSource.enrich()` and `SocialSignalSource.get_hn_points()` accept `httpx.AsyncClient` as a parameter instead of creating their own.

### 4. Smarter Text Truncation (`scipaper/text_utils.py`)

New utility: `prepare_text_for_llm(full_text: str, max_chars: int = 15000) -> str`

Steps:

1. Strip everything after "References", "Bibliography", or "Appendix" headings
2. Strip "Acknowledgments" / "Acknowledgements" section
3. Truncate to `max_chars` at the nearest sentence boundary
4. Preserve Abstract, all numbered sections, Tables, and Figures references

Replaces `full_text[:15000]` in `writer.py` and `checker.py`.

### 5. Drop LLM Quick Takes

In `edition.py`:

- `generate_quick_take()` becomes a wrapper around `_fallback_quick_take()` (no LLM)
- Remove the Anthropic/OpenAI client creation code from this function
- Remove `llm_provider`, `llm_model`, `anthropic_api_key`, `openai_api_key` from `AssemblyConfig`

The fallback already extracts the first sentence of the abstract, which is sufficient for 50-word Quick Take summaries.

### 6. Fix Model Version Drift

`config/__init__.py` `SignalConfig.llm_model` becomes the single source of truth.

All module-level config dataclasses (`ScoringConfig`, `GenerationConfig`, `VerificationConfig`) default their `llm_model` to `None`. At runtime, `pipeline.py` propagates `SignalConfig.llm_model` into each stage config.

Update `config/__init__.py` default from `claude-3-5-sonnet-20241022` to `claude-sonnet-4-20250514`.

### 7. SQLite Cache Layer (`scipaper/cache.py`)

Schema:

```sql
CREATE TABLE cache (
    key TEXT PRIMARY KEY,    -- "{arxiv_id}:{stage}:{model_version}"
    stage TEXT,              -- "score", "generate", "verify"
    data TEXT,               -- JSON-serialized result
    created_at TEXT,
    model_version TEXT
);
```

Cache integration points:

- `score_narrative_potential()` — cache by `(arxiv_id, "score", model)`
- `generate_piece()` — cache by `(arxiv_id, "generate", model)`
- `verify_piece()` — cache by `(arxiv_id, "verify", model)`

Cache is invalidated when model version changes. Optional `--no-cache` CLI flag to force fresh run.

Store at `data/cache.db` (gitignored).

### 8. Retry Expansion

Extend `retry.py` `_RETRYABLE` tuple to include:

- `httpx.HTTPStatusError` where status is 429 or 503
- `anthropic.RateLimitError`
- `anthropic.InternalServerError`

Add a custom retry callback that respects `Retry-After` header on 429 responses.

## Files Changed

| File                           | Type | Changes                                     |
| ------------------------------ | ---- | ------------------------------------------- |
| `scipaper/clients.py`          | New  | `ClientPool` context manager                |
| `scipaper/cache.py`            | New  | SQLite cache layer                          |
| `scipaper/text_utils.py`       | New  | `prepare_text_for_llm()`                    |
| `scipaper/config/__init__.py`  | Edit | Fix model default, single source of truth   |
| `scipaper/curate/ingest.py`    | Edit | Accept shared client, concurrent enrichment |
| `scipaper/curate/score.py`     | Edit | Two-pass scoring, accept shared client      |
| `scipaper/generate/writer.py`  | Edit | Accept shared client, smart truncation      |
| `scipaper/generate/edition.py` | Edit | Remove LLM quick takes                      |
| `scipaper/verify/checker.py`   | Edit | Accept shared client, smart truncation      |
| `scipaper/pipeline.py`         | Edit | Wire ClientPool, two-pass, concurrency      |
| `scipaper/retry.py`            | Edit | Handle 429/503/RateLimitError               |
| `scipaper/__main__.py`         | Edit | Add `--no-cache` flag                       |
| `.gitignore`                   | Edit | Add `data/cache.db`                         |
| Tests (multiple)               | Edit | Update for new function signatures          |

## Expected Impact

| Metric                       | Before                     | After                           |
| ---------------------------- | -------------------------- | ------------------------------- |
| LLM calls per run            | ~230                       | ~35                             |
| Enrichment time (200 papers) | ~200s sequential           | ~20s concurrent                 |
| Scoring time                 | ~200s (200 sequential LLM) | ~10s (20 concurrent LLM)        |
| Generation + verification    | ~60s sequential            | ~40s (client reuse)             |
| Full pipeline re-run         | Full cost                  | Near-zero (cached)              |
| Rate limit risk              | High (no protection)       | Controlled (semaphores + retry) |

## Risks

- **Two-pass scoring changes ranking** — papers that score low on relevance but high on narrative potential will be missed. Mitigated by setting `relevance_cutoff_count=20` (4x the selection count of 5).
- **Cache staleness** — a paper's citation count or social signals could change. Acceptable for a weekly pipeline; cache is per-model-version and can be bypassed with `--no-cache`.
- **Concurrent LLM calls** — Anthropic rate limits vary by tier. Semaphore of 5 is conservative. Can be tuned via config.
