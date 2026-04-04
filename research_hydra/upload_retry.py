from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

import httpx
from hydra_db.core.api_error import ApiError

T = TypeVar("T")

_RETRYABLE = frozenset({429, 502, 503, 504, 520, 524})
_DEFAULT_ATTEMPTS = 6


def _backoff_api(attempt: int, code: int) -> float:
    base = 2.0 * (2**attempt)
    if code == 429:
        return max(base, 8.0)
    if code in (524, 502, 503):
        return max(base, 15.0 + 12.0 * attempt)
    return base


def _backoff_http(attempt: int) -> float:
    return max(2.0 * (2**attempt), 10.0 + 8.0 * attempt)


async def run_with_upload_retries(
    op: Callable[[], Awaitable[T]],
    *,
    logger: logging.Logger,
    max_attempts: int = _DEFAULT_ATTEMPTS,
) -> T:
    last = max_attempts - 1
    for attempt in range(max_attempts):
        try:
            return await op()
        except ApiError as e:
            code = e.status_code or 0
            if attempt >= last or code not in _RETRYABLE:
                raise
            wait = _backoff_api(attempt, code)
            logger.warning(
                "Hydra upload HTTP %s (attempt %s/%s), sleep %ss",
                code,
                attempt + 1,
                max_attempts,
                wait,
            )
            await asyncio.sleep(wait)
        except (
            httpx.ReadTimeout,
            httpx.WriteTimeout,
            httpx.ConnectTimeout,
            httpx.TimeoutException,
        ) as e:
            if attempt >= last:
                raise
            wait = _backoff_http(attempt)
            logger.warning(
                "Hydra upload timeout (attempt %s/%s), sleep %ss: %s",
                attempt + 1,
                max_attempts,
                wait,
                e,
            )
            await asyncio.sleep(wait)
    raise RuntimeError("unreachable")
