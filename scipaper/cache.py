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
