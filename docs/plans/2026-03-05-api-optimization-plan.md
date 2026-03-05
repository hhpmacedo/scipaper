# API Architecture Optimization — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Cut LLM calls from ~230 to ~35, add concurrency, client reuse, caching, and rate limiting to the Signal pipeline.

**Architecture:** Two-pass scoring (relevance filter → LLM only for top 20), shared `ClientPool` for all HTTP/LLM calls, SQLite cache for idempotent re-runs, semaphore-based rate limiting for external APIs.

**Tech Stack:** Python 3.10+, httpx, anthropic SDK, aiosqlite, asyncio, tenacity

---

### Task 1: Smarter Text Truncation

New utility to replace naive `[:15000]` truncation. No dependencies on other tasks.

**Files:**

- Create: `scipaper/text_utils.py`
- Create: `tests/test_text_utils.py`
- Modify: `scipaper/generate/writer.py:127`
- Modify: `scipaper/verify/checker.py:177`

**Step 1: Write the failing tests**

```python
# tests/test_text_utils.py
"""Tests for text truncation utility."""


def test_strips_references_section():
    text = "Abstract\n\nSome content.\n\n1 Introduction\n\nIntro text.\n\nReferences\n\n[1] Doe et al."
    from scipaper.text_utils import prepare_text_for_llm
    result = prepare_text_for_llm(text, max_chars=5000)
    assert "[1] Doe et al." not in result
    assert "Some content." in result


def test_strips_acknowledgments():
    text = "Content here.\n\nAcknowledgments\n\nThanks to everyone.\n\n2 Methods\n\nMore content."
    from scipaper.text_utils import prepare_text_for_llm
    result = prepare_text_for_llm(text)
    assert "Thanks to everyone" not in result
    assert "Content here." in result


def test_truncates_at_sentence_boundary():
    text = "First sentence. Second sentence. Third sentence. Fourth sentence."
    from scipaper.text_utils import prepare_text_for_llm
    result = prepare_text_for_llm(text, max_chars=40)
    assert result.endswith(".")
    assert len(result) <= 40


def test_preserves_abstract_and_sections():
    text = "Abstract\n\nThis is the abstract.\n\n1 Introduction\n\nIntro.\n\n2 Methods\n\nMethods text."
    from scipaper.text_utils import prepare_text_for_llm
    result = prepare_text_for_llm(text, max_chars=5000)
    assert "This is the abstract." in result
    assert "Methods text." in result


def test_handles_empty_text():
    from scipaper.text_utils import prepare_text_for_llm
    assert prepare_text_for_llm("") == ""


def test_handles_text_shorter_than_max():
    from scipaper.text_utils import prepare_text_for_llm
    short = "Short text."
    assert prepare_text_for_llm(short, max_chars=5000) == short


def test_strips_bibliography_variant():
    text = "Content.\n\nBibliography\n\n[1] Smith 2024."
    from scipaper.text_utils import prepare_text_for_llm
    result = prepare_text_for_llm(text, max_chars=5000)
    assert "[1] Smith 2024." not in result


def test_strips_appendix():
    text = "Content.\n\nAppendix A\n\nSupplementary material."
    from scipaper.text_utils import prepare_text_for_llm
    result = prepare_text_for_llm(text, max_chars=5000)
    assert "Supplementary material" not in result
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_text_utils.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scipaper.text_utils'`

**Step 3: Write the implementation**

```python
# scipaper/text_utils.py
"""Utilities for preparing paper text for LLM consumption."""

import re


# Sections to strip before sending to LLM (case-insensitive, match at line start)
_STRIP_SECTIONS = re.compile(
    r'^(References|Bibliography|Acknowledgments?|Acknowledgements?|Appendix(?:\s+[A-Z])?)[\s:]*$',
    re.MULTILINE | re.IGNORECASE,
)


def prepare_text_for_llm(full_text: str, max_chars: int = 15000) -> str:
    """
    Prepare paper full text for LLM input.

    1. Strip References/Bibliography/Acknowledgments/Appendix sections
    2. Truncate to max_chars at nearest sentence boundary
    """
    if not full_text:
        return ""

    # Find the earliest strippable section and cut there
    match = _STRIP_SECTIONS.search(full_text)
    if match:
        full_text = full_text[:match.start()].rstrip()

    if len(full_text) <= max_chars:
        return full_text

    # Truncate at sentence boundary
    truncated = full_text[:max_chars]
    last_period = truncated.rfind(". ")
    if last_period > max_chars // 2:
        return truncated[:last_period + 1]

    return truncated.rstrip()
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_text_utils.py -v`
Expected: All PASS

**Step 5: Wire into writer.py and checker.py**

In `scipaper/generate/writer.py:127`, replace:

```python
full_text=paper.full_text[:15000],
```

with:

```python
from ..text_utils import prepare_text_for_llm
...
full_text=prepare_text_for_llm(paper.full_text),
```

In `scipaper/verify/checker.py:177`, same replacement:

```python
paper_full_text=prepare_text_for_llm(paper.full_text),
```

**Step 6: Run existing tests**

Run: `pytest tests/test_writer.py tests/test_checker.py tests/test_text_utils.py -v`
Expected: All PASS

**Step 7: Commit**

```bash
git add scipaper/text_utils.py tests/test_text_utils.py scipaper/generate/writer.py scipaper/verify/checker.py
git commit -m "feat: add smart text truncation for LLM input"
```

---

### Task 2: Retry Expansion (429, 503, Anthropic errors)

Extend `api_retry` to handle rate limits and server errors.

**Files:**

- Modify: `scipaper/retry.py`
- Modify: `tests/test_retry.py`

**Step 1: Write the failing tests**

Add to `tests/test_retry.py`:

```python
@pytest.mark.asyncio
async def test_retries_on_http_429():
    """HTTP 429 (rate limited) is retryable."""
    import httpx

    call_count = 0

    @_fast_retry
    async def rate_limited():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            response = httpx.Response(429, request=httpx.Request("GET", "https://example.com"))
            raise httpx.HTTPStatusError("rate limited", request=response.request, response=response)
        return "ok"

    assert await rate_limited() == "ok"
    assert call_count == 3


@pytest.mark.asyncio
async def test_retries_on_http_503():
    """HTTP 503 (service unavailable) is retryable."""
    import httpx

    call_count = 0

    @_fast_retry
    async def unavailable():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            response = httpx.Response(503, request=httpx.Request("GET", "https://example.com"))
            raise httpx.HTTPStatusError("unavailable", request=response.request, response=response)
        return "ok"

    assert await unavailable() == "ok"
    assert call_count == 3


@pytest.mark.asyncio
async def test_does_not_retry_http_400():
    """HTTP 400 (bad request) is NOT retryable."""
    import httpx

    call_count = 0

    @_fast_retry
    async def bad_request():
        nonlocal call_count
        call_count += 1
        response = httpx.Response(400, request=httpx.Request("GET", "https://example.com"))
        raise httpx.HTTPStatusError("bad request", request=response.request, response=response)

    with pytest.raises(httpx.HTTPStatusError):
        await bad_request()

    assert call_count == 1


@pytest.mark.asyncio
async def test_retries_on_anthropic_rate_limit():
    """anthropic.RateLimitError is retryable."""
    call_count = 0

    @_fast_retry
    async def anthropic_limited():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            from scipaper.retry import RateLimitSentinel
            raise RateLimitSentinel("rate limited")
        return "ok"

    assert await anthropic_limited() == "ok"
    assert call_count == 3
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_retry.py -v -k "429 or 503 or 400 or anthropic_rate"`
Expected: FAIL

**Step 3: Update retry.py**

```python
# scipaper/retry.py
"""
Shared retry decorator for external API calls.

Applies exponential backoff on transient network errors (ConnectionError,
TimeoutError, httpx equivalents, HTTP 429/503, Anthropic rate limits).
Max 3 attempts with 1-8s wait window.
"""

import logging

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

logger = logging.getLogger(__name__)


class RateLimitSentinel(Exception):
    """Raised as a stand-in when anthropic.RateLimitError is not importable."""
    pass


def _is_retryable(exc: BaseException) -> bool:
    """Return True if the exception is transient and worth retrying."""
    # Network-level errors
    if isinstance(exc, (ConnectionError, TimeoutError, httpx.ConnectError, httpx.TimeoutException)):
        return True

    # HTTP status errors: only retry 429 and 503
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 503)

    # Anthropic SDK errors (imported lazily to avoid hard dependency)
    if isinstance(exc, RateLimitSentinel):
        return True

    try:
        import anthropic
        if isinstance(exc, (anthropic.RateLimitError, anthropic.InternalServerError)):
            return True
    except ImportError:
        pass

    return False


api_retry = retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
```

**Step 4: Run all retry tests**

Run: `pytest tests/test_retry.py -v`
Expected: All PASS (old and new)

**Step 5: Commit**

```bash
git add scipaper/retry.py tests/test_retry.py
git commit -m "feat: extend retry to handle 429/503 and Anthropic rate limits"
```

---

### Task 3: Shared Client Pool

New module for shared HTTP and LLM clients.

**Files:**

- Create: `scipaper/clients.py`
- Create: `tests/test_clients.py`

**Step 1: Write the failing tests**

```python
# tests/test_clients.py
"""Tests for shared client pool."""

from .conftest import run_async


def test_client_pool_creates_httpx_client():
    from scipaper.clients import ClientPool

    async def _test():
        async with ClientPool() as pool:
            assert pool.http is not None
            assert not pool.http.is_closed

    run_async(_test())


def test_client_pool_closes_on_exit():
    from scipaper.clients import ClientPool

    async def _test():
        pool = ClientPool()
        async with pool:
            http = pool.http
        assert http.is_closed

    run_async(_test())


def test_client_pool_creates_anthropic_client():
    from scipaper.clients import ClientPool

    async def _test():
        async with ClientPool(anthropic_api_key="test-key") as pool:
            assert pool.anthropic is not None

    run_async(_test())


def test_client_pool_anthropic_none_without_key():
    from scipaper.clients import ClientPool

    async def _test():
        async with ClientPool() as pool:
            assert pool.anthropic is None

    run_async(_test())
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_clients.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write implementation**

```python
# scipaper/clients.py
"""Shared API client pool for the Signal pipeline."""

from typing import Optional

import httpx


class ClientPool:
    """
    Async context manager holding shared HTTP and LLM clients.

    Usage:
        async with ClientPool(anthropic_api_key="sk-...") as pool:
            response = await pool.http.get("https://...")
            llm_response = await pool.anthropic.messages.create(...)
    """

    def __init__(
        self,
        anthropic_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        http_timeout: float = 30.0,
    ):
        self._anthropic_api_key = anthropic_api_key
        self._openai_api_key = openai_api_key
        self._http_timeout = http_timeout
        self.http: Optional[httpx.AsyncClient] = None
        self.anthropic = None
        self.openai = None

    async def __aenter__(self) -> "ClientPool":
        self.http = httpx.AsyncClient(timeout=self._http_timeout, follow_redirects=True)

        if self._anthropic_api_key:
            import anthropic
            self.anthropic = anthropic.AsyncAnthropic(api_key=self._anthropic_api_key)

        if self._openai_api_key:
            from openai import AsyncOpenAI
            self.openai = AsyncOpenAI(api_key=self._openai_api_key)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.http:
            await self.http.aclose()
        # Anthropic and OpenAI async clients don't require explicit close
        return False
```

**Step 4: Run tests**

Run: `pytest tests/test_clients.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add scipaper/clients.py tests/test_clients.py
git commit -m "feat: add shared ClientPool for HTTP and LLM clients"
```

---

### Task 4: SQLite Cache Layer

Cache LLM results keyed by arxiv_id, stage, and model version.

**Files:**

- Create: `scipaper/cache.py`
- Create: `tests/test_cache.py`
- Modify: `.gitignore`

**Step 1: Write the failing tests**

```python
# tests/test_cache.py
"""Tests for the SQLite cache layer."""

import json
import tempfile
from pathlib import Path

from .conftest import run_async


def test_cache_set_and_get():
    from scipaper.cache import PipelineCache

    async def _test():
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            async with PipelineCache(db_path) as cache:
                await cache.set("paper1", "score", "model-v1", {"score": 7.5})
                result = await cache.get("paper1", "score", "model-v1")
                assert result == {"score": 7.5}

    run_async(_test())


def test_cache_miss_returns_none():
    from scipaper.cache import PipelineCache

    async def _test():
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            async with PipelineCache(db_path) as cache:
                result = await cache.get("nonexistent", "score", "model-v1")
                assert result is None

    run_async(_test())


def test_cache_different_model_is_miss():
    from scipaper.cache import PipelineCache

    async def _test():
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            async with PipelineCache(db_path) as cache:
                await cache.set("paper1", "score", "model-v1", {"score": 7.5})
                result = await cache.get("paper1", "score", "model-v2")
                assert result is None

    run_async(_test())


def test_cache_overwrite():
    from scipaper.cache import PipelineCache

    async def _test():
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            async with PipelineCache(db_path) as cache:
                await cache.set("paper1", "score", "model-v1", {"score": 5.0})
                await cache.set("paper1", "score", "model-v1", {"score": 8.0})
                result = await cache.get("paper1", "score", "model-v1")
                assert result == {"score": 8.0}

    run_async(_test())


def test_cache_clear():
    from scipaper.cache import PipelineCache

    async def _test():
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            async with PipelineCache(db_path) as cache:
                await cache.set("paper1", "score", "model-v1", {"score": 7.5})
                await cache.clear()
                result = await cache.get("paper1", "score", "model-v1")
                assert result is None

    run_async(_test())
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cache.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write implementation**

```python
# scipaper/cache.py
"""SQLite cache for pipeline LLM results."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import aiosqlite

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cache (
    key TEXT PRIMARY KEY,
    arxiv_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    model_version TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cache_lookup ON cache(arxiv_id, stage, model_version);
"""


class PipelineCache:
    """
    Async context manager for SQLite-backed pipeline cache.

    Usage:
        async with PipelineCache(Path("data/cache.db")) as cache:
            cached = await cache.get("2403.12345", "score", "claude-sonnet-4")
            if cached is None:
                result = await expensive_llm_call(...)
                await cache.set("2403.12345", "score", "claude-sonnet-4", result)
    """

    def __init__(self, db_path: Path = Path("data/cache.db")):
        self._db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    def _make_key(self, arxiv_id: str, stage: str, model_version: str) -> str:
        return f"{arxiv_id}:{stage}:{model_version}"

    async def __aenter__(self) -> "PipelineCache":
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self._db_path))
        await self._db.executescript(_SCHEMA)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._db:
            await self._db.close()
        return False

    async def get(self, arxiv_id: str, stage: str, model_version: str) -> Optional[Any]:
        key = self._make_key(arxiv_id, stage, model_version)
        async with self._db.execute(
            "SELECT data FROM cache WHERE key = ?", (key,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return json.loads(row[0])
        return None

    async def set(self, arxiv_id: str, stage: str, model_version: str, data: Any) -> None:
        key = self._make_key(arxiv_id, stage, model_version)
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            """INSERT OR REPLACE INTO cache (key, arxiv_id, stage, model_version, data, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (key, arxiv_id, stage, model_version, json.dumps(data), now),
        )
        await self._db.commit()

    async def clear(self) -> None:
        await self._db.execute("DELETE FROM cache")
        await self._db.commit()
        logger.info("Cache cleared")
```

**Step 4: Run tests**

Run: `pytest tests/test_cache.py -v`
Expected: All PASS

**Step 5: Add cache.db to .gitignore**

Append to `.gitignore`:

```
# Cache
data/cache.db
```

**Step 6: Commit**

```bash
git add scipaper/cache.py tests/test_cache.py .gitignore
git commit -m "feat: add SQLite cache layer for pipeline LLM results"
```

---

### Task 5: Fix Model Version Drift

Single source of truth for LLM model in `config/__init__.py`.

**Files:**

- Modify: `scipaper/config/__init__.py`
- Modify: `scipaper/curate/score.py`
- Modify: `scipaper/generate/writer.py`
- Modify: `scipaper/generate/edition.py`
- Modify: `scipaper/verify/checker.py`

**Step 1: Update config/**init**.py**

Change line 29:

```python
llm_model: str = "claude-sonnet-4-20250514"
```

**Step 2: Update module configs to default to None**

In `scipaper/curate/score.py` `ScoringConfig`:

```python
llm_model: Optional[str] = None  # Inherits from SignalConfig
```

In `scipaper/generate/writer.py` `GenerationConfig`:

```python
llm_model: Optional[str] = None  # Inherits from SignalConfig
```

In `scipaper/verify/checker.py` `VerificationConfig`:

```python
llm_model: Optional[str] = None  # Inherits from SignalConfig
```

**Step 3: Add model resolution to each LLM-calling function**

At the top of `_score_with_anthropic`, `_generate_with_anthropic`, `_verify_with_anthropic`, add:

```python
model = config.llm_model or "claude-sonnet-4-20250514"
```

And use `model` instead of `config.llm_model` in the API call.

**Step 4: Run full test suite**

Run: `pytest -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add scipaper/config/__init__.py scipaper/curate/score.py scipaper/generate/writer.py scipaper/generate/edition.py scipaper/verify/checker.py
git commit -m "fix: single source of truth for LLM model version"
```

---

### Task 6: Drop LLM Quick Takes

Replace LLM-based quick take generation with the existing fallback.

**Files:**

- Modify: `scipaper/generate/edition.py`
- Modify: `tests/test_edition.py`

**Step 1: Simplify generate_quick_take**

Replace the entire `generate_quick_take` function body with:

```python
async def generate_quick_take(
    paper: ScoredPaper,
    config: Optional[AssemblyConfig] = None
) -> QuickTake:
    """Generate a brief summary for a runner-up paper."""
    return _fallback_quick_take(paper)
```

**Step 2: Remove LLM fields from AssemblyConfig**

```python
@dataclass
class AssemblyConfig:
    """Configuration for edition assembly."""
    max_pieces: int = 5
    max_quick_takes: int = 5
    target_word_count: int = 5000
```

Remove `llm_provider`, `llm_model`, `anthropic_api_key`, `openai_api_key` fields.

**Step 3: Clean up imports**

Remove unused `anthropic` and `openai` imports from `edition.py`.

**Step 4: Run edition tests**

Run: `pytest tests/test_edition.py -v`
Expected: All PASS (update any tests that pass LLM-related config to AssemblyConfig)

**Step 5: Commit**

```bash
git add scipaper/generate/edition.py tests/test_edition.py
git commit -m "refactor: drop LLM quick takes, use abstract extraction"
```

---

### Task 7: Concurrent Enrichment in Ingest

Add asyncio.gather + semaphores for Semantic Scholar and HN lookups. Accept shared httpx client.

**Files:**

- Modify: `scipaper/curate/ingest.py`
- Modify: `tests/test_ingest.py`

**Step 1: Write new tests for concurrent enrichment**

Add to `tests/test_ingest.py`:

```python
def test_ingest_papers_concurrent(self):
    """Verify ingest_papers runs enrichment concurrently."""
    from unittest.mock import call

    papers = [make_paper(arxiv_id=str(i)) for i in range(5)]

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "citationCount": 1, "referenceCount": 1, "externalIds": {},
    }
    mock_response.raise_for_status = MagicMock()

    hn_response = MagicMock()
    hn_response.status_code = 200
    hn_response.json.return_value = {"hits": []}

    with patch("scipaper.curate.ingest.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[mock_response, hn_response] * 5)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_client

        with patch("scipaper.curate.ingest.ArxivSource.fetch", new_callable=AsyncMock, return_value=papers):
            result = run_async(ingest_papers())

    assert len(result) == 5
```

**Step 2: Refactor SemanticScholarSource.enrich to accept optional client**

```python
async def enrich(self, paper: Paper, client: Optional[httpx.AsyncClient] = None) -> Paper:
    headers = {}
    if self.api_key:
        headers["x-api-key"] = self.api_key

    url = (
        f"{self.BASE_URL}/paper/ArXiv:{paper.arxiv_id}"
        f"?fields=citationCount,referenceCount,externalIds"
    )

    try:
        if client:
            response = await client.get(url, headers=headers, timeout=10.0)
        else:
            async with httpx.AsyncClient(timeout=10.0) as c:
                response = await c.get(url, headers=headers)

        if response.status_code == 404:
            return paper
        response.raise_for_status()
        data = response.json()
        paper.citation_count = data.get("citationCount", 0) or 0
        paper.reference_count = data.get("referenceCount", 0) or 0
        ext_ids = data.get("externalIds", {})
        if ext_ids:
            paper.semantic_scholar_id = ext_ids.get("CorpusId")
    except httpx.HTTPError as e:
        logger.warning(f"Semantic Scholar lookup failed for {paper.arxiv_id}: {e}")

    return paper
```

**Step 3: Same for SocialSignalSource.get_hn_points**

Add optional `client` parameter, use it if provided, else create fresh client.

**Step 4: Make ingest_papers concurrent**

```python
async def ingest_papers(config: IngestConfig = None, client: Optional[httpx.AsyncClient] = None) -> List[Paper]:
    config = config or IngestConfig()

    arxiv = ArxivSource(config)
    papers = await arxiv.fetch()

    semantic = SemanticScholarSource()
    social = SocialSignalSource()

    sem_scholar = asyncio.Semaphore(10)
    sem_hn = asyncio.Semaphore(5)

    async def _enrich_one(paper):
        async with sem_scholar:
            try:
                paper = await semantic.enrich(paper, client)
            except Exception as e:
                logger.warning(f"Failed to enrich {paper.arxiv_id}: {e}")
        async with sem_hn:
            try:
                paper.hn_points = await social.get_hn_points(paper, client)
            except Exception:
                pass
        return paper

    enriched = await asyncio.gather(*[_enrich_one(p) for p in papers])

    logger.info(f"Ingestion complete: {len(enriched)} papers processed")
    return list(enriched)
```

**Step 5: Run tests**

Run: `pytest tests/test_ingest.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add scipaper/curate/ingest.py tests/test_ingest.py
git commit -m "feat: concurrent enrichment with semaphore rate limiting"
```

---

### Task 8: Two-Pass Scoring

Split scoring into relevance-first pass (pure Python) and LLM-only for top N.

**Files:**

- Modify: `scipaper/curate/score.py`
- Modify: `tests/test_score.py`

**Step 1: Write tests for two-pass scoring**

Add to `tests/test_score.py`:

```python
class TestTwoPassScoring:
    def test_only_top_n_get_narrative_scored(self):
        """Only top N by relevance should have LLM narrative scoring called."""
        papers = [
            make_paper(arxiv_id=str(i), title=f"Paper {i}", abstract=f"Abstract {i}")
            for i in range(10)
        ]
        anchor = make_anchor()

        llm_call_count = 0

        async def mock_score_anthropic(prompt, config):
            nonlocal llm_call_count
            llm_call_count += 1
            return 5.0

        async def run_test():
            with patch("scipaper.curate.score._score_with_anthropic", side_effect=mock_score_anthropic):
                from scipaper.curate.score import score_papers_two_pass, ScoringConfig
                config = ScoringConfig(relevance_cutoff_count=3)
                return await score_papers_two_pass(papers, anchor, config)

        scored = run_async(run_test())
        assert llm_call_count == 3  # Only top 3 got LLM scoring
        assert len(scored) == 10  # All papers returned

    def test_two_pass_sorts_by_composite(self):
        papers = [
            make_paper(arxiv_id="1", title="Irrelevant", abstract="Fluid dynamics"),
            make_paper(arxiv_id="2", title="Reasoning model scaling", abstract="Test-time compute for reasoning"),
        ]
        anchor = make_anchor()

        async def run_test():
            with patch("scipaper.curate.score._score_with_anthropic", side_effect=Exception("no api")):
                from scipaper.curate.score import score_papers_two_pass
                return await score_papers_two_pass(papers, anchor)

        scored = run_async(run_test())
        assert scored[0].composite_score >= scored[1].composite_score
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_score.py::TestTwoPassScoring -v`
Expected: FAIL — `cannot import name 'score_papers_two_pass'`

**Step 3: Add relevance_cutoff_count to ScoringConfig**

```python
relevance_cutoff_count: int = 20
```

**Step 4: Implement score_papers_two_pass**

```python
async def score_papers_two_pass(
    papers: List[Paper],
    anchor: AnchorDocument,
    config: Optional[ScoringConfig] = None,
) -> List[ScoredPaper]:
    """
    Two-pass scoring: relevance first (pure Python), then LLM narrative
    only for the top N candidates.
    """
    config = config or ScoringConfig()

    # Pass 1: score relevance for all papers (no LLM, instant)
    relevance_scores = {}
    for paper in papers:
        relevance_scores[paper.arxiv_id] = await score_relevance(paper, anchor, config)

    # Rank by relevance, take top N for LLM scoring
    sorted_by_relevance = sorted(papers, key=lambda p: relevance_scores[p.arxiv_id], reverse=True)
    top_candidates = sorted_by_relevance[:config.relevance_cutoff_count]
    rest = sorted_by_relevance[config.relevance_cutoff_count:]

    # Pass 2: LLM narrative scoring for top candidates only
    scored = []

    sem = asyncio.Semaphore(5)

    async def _score_one(paper):
        async with sem:
            narrative = await score_narrative_potential(paper, config)
        relevance = relevance_scores[paper.arxiv_id]
        composite = compute_composite_score(relevance, narrative)
        return ScoredPaper(
            paper=paper,
            relevance_score=relevance,
            narrative_potential_score=narrative,
            composite_score=composite,
        )

    scored = await asyncio.gather(*[_score_one(p) for p in top_candidates])
    scored = list(scored)

    # Rest get heuristic narrative score
    for paper in rest:
        relevance = relevance_scores[paper.arxiv_id]
        narrative = _heuristic_narrative_score(paper)
        composite = compute_composite_score(relevance, narrative)
        scored.append(ScoredPaper(
            paper=paper,
            relevance_score=relevance,
            narrative_potential_score=narrative,
            composite_score=composite,
        ))

    scored.sort(key=lambda x: x.composite_score, reverse=True)
    logger.info(f"Two-pass scored {len(scored)} papers ({len(top_candidates)} with LLM)")
    return scored
```

Add `import asyncio` to the imports.

**Step 5: Run tests**

Run: `pytest tests/test_score.py -v`
Expected: All PASS (old `score_papers` tests still pass, new two-pass tests pass)

**Step 6: Commit**

```bash
git add scipaper/curate/score.py tests/test_score.py
git commit -m "feat: two-pass scoring — relevance filter then LLM for top N"
```

---

### Task 9: Wire Everything into Pipeline

Connect ClientPool, two-pass scoring, cache, and concurrency into `pipeline.py` and `__main__.py`.

**Files:**

- Modify: `scipaper/pipeline.py`
- Modify: `scipaper/__main__.py`
- Modify: `tests/test_pipeline.py`

**Step 1: Update PipelineConfig**

Add to `PipelineConfig`:

```python
use_cache: bool = True
cache_db_path: Path = Path("data/cache.db")
```

**Step 2: Update run_pipeline signature**

```python
async def run_pipeline(
    anchor: AnchorDocument,
    config: Optional[PipelineConfig] = None,
    papers: Optional[List[Paper]] = None,
    clients: Optional["ClientPool"] = None,
) -> PipelineResult:
```

If `clients` is None, create a `ClientPool` internally (backwards compatible).

**Step 3: Replace score_papers with score_papers_two_pass in pipeline**

Line 99: change `score_papers` import and call to `score_papers_two_pass`.

**Step 4: Add concurrent PDF downloads**

Replace the sequential for-loop (lines 114-135) with `asyncio.gather`:

```python
sem_pdf = asyncio.Semaphore(3)

async def _download_and_generate(sp):
    async with sem_pdf:
        paper = sp.paper
        if not paper.full_text and not config.skip_pdf_download:
            pdf_path = await download_paper_pdf(paper.arxiv_id, config.pdf_cache_dir)
            parsed = await parse_paper_pdf(pdf_path, paper.arxiv_id, config.parser)
            paper.full_text = parsed.full_text
        if not paper.full_text:
            return None
        piece = await generate_piece(paper, config.generation)
        return (piece, paper)

results = await asyncio.gather(*[_download_and_generate(sp) for sp in selected], return_exceptions=True)
```

**Step 5: Add --no-cache to **main**.py**

```python
parser.add_argument(
    "--no-cache",
    action="store_true",
    default=False,
    help="Bypass cache and force fresh LLM calls",
)
```

Pass `use_cache=not args.no_cache` to `PipelineConfig`.

**Step 6: Run pipeline tests**

Run: `pytest tests/test_pipeline.py -v`
Expected: All PASS

**Step 7: Run full test suite**

Run: `pytest -v`
Expected: All PASS

**Step 8: Commit**

```bash
git add scipaper/pipeline.py scipaper/__main__.py tests/test_pipeline.py
git commit -m "feat: wire ClientPool, two-pass scoring, cache, and concurrency into pipeline"
```

---

### Task 10: Final Verification

**Step 1: Run full test suite**

Run: `pytest -v`
Expected: All PASS, no regressions

**Step 2: Run linting**

Run: `ruff check .`
Expected: Clean

**Step 3: Verify imports are clean**

Run: `python -c "from scipaper.pipeline import run_pipeline; print('OK')"`
Expected: `OK`

**Step 4: Commit any fixes**

```bash
git add -A
git commit -m "chore: lint fixes for API optimization"
```
