"""
Shared retry decorator for external API calls.

Applies exponential backoff on transient network errors (ConnectionError,
TimeoutError, and httpx equivalents). Max 3 attempts with 1-8s wait window.
"""

import logging

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

logger = logging.getLogger(__name__)

# Retry on standard Python network errors and httpx-specific equivalents.
_RETRYABLE = (
    ConnectionError,
    TimeoutError,
    httpx.ConnectError,
    httpx.TimeoutException,
)

api_retry = retry(
    retry=retry_if_exception_type(_RETRYABLE),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
