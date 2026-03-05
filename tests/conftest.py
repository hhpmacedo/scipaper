"""
Test configuration.

Provides a helper to run async functions without asyncio.run(),
which fails due to the `signal` module name collision.
"""
import asyncio

import pytest


def run_async(coro):
    """
    Run an async coroutine synchronously.

    Uses loop.run_until_complete() instead of asyncio.run()
    to avoid the signal module name collision (asyncio.run tries
    to access signal.getsignal from stdlib, but finds our package).
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
