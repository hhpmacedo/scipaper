"""
Tests for the shared api_retry decorator.

Uses wait_none() to avoid real backoff delays in tests.
"""

import pytest
from tenacity import wait_none

from scipaper.retry import api_retry


def _fast_retry(func):
    """Apply api_retry but override wait to zero for fast tests."""
    decorated = api_retry(func)
    decorated.retry.wait = wait_none()
    return decorated


# ── Tests ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_succeeds_on_first_try():
    """Decorated function that succeeds immediately returns the correct value."""

    @_fast_retry
    async def succeeds():
        return "ok"

    assert await succeeds() == "ok"


@pytest.mark.asyncio
async def test_retries_on_connection_error():
    """Fails twice with ConnectionError then succeeds on third attempt."""
    call_count = 0

    @_fast_retry
    async def flaky():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("temporary failure")
        return "recovered"

    assert await flaky() == "recovered"
    assert call_count == 3


@pytest.mark.asyncio
async def test_gives_up_after_max_retries():
    """Always raises ConnectionError — should exhaust retries and re-raise."""

    @_fast_retry
    async def always_fails():
        raise ConnectionError("connection refused")

    with pytest.raises(ConnectionError):
        await always_fails()


@pytest.mark.asyncio
async def test_does_not_retry_value_error():
    """ValueError is not a retryable exception — should raise immediately."""
    call_count = 0

    @_fast_retry
    async def raises_once():
        nonlocal call_count
        call_count += 1
        raise ValueError("not retryable")

    with pytest.raises(ValueError):
        await raises_once()

    assert call_count == 1


@pytest.mark.asyncio
async def test_retries_on_timeout_error():
    """TimeoutError is retryable."""
    call_count = 0

    @_fast_retry
    async def times_out_twice():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise TimeoutError("timed out")
        return "done"

    assert await times_out_twice() == "done"
    assert call_count == 3


@pytest.mark.asyncio
async def test_retries_on_httpx_connect_error():
    """httpx.ConnectError is retryable."""
    import httpx

    call_count = 0

    @_fast_retry
    async def httpx_connect_fails():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise httpx.ConnectError("connect failed")
        return "connected"

    assert await httpx_connect_fails() == "connected"
    assert call_count == 3


@pytest.mark.asyncio
async def test_retries_on_httpx_timeout():
    """httpx.TimeoutException is retryable."""
    import httpx

    call_count = 0

    @_fast_retry
    async def httpx_times_out():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise httpx.TimeoutException("timeout")
        return "done"

    assert await httpx_times_out() == "done"
    assert call_count == 3


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
