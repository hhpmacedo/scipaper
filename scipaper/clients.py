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
        return False
