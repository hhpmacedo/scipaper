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
