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
