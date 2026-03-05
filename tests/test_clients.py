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
