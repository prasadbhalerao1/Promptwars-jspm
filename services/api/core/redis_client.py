"""Shared async Redis client, used by the rate limiter.

Redis is optional: if it can't be reached, `get_redis()` returns None and callers fall
back to in-process behaviour. A failed connection latches off so a down Redis costs one
timeout per process rather than one per request.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from services.api.core.config import get_settings

logger = logging.getLogger(__name__)

# Redis is either up on localhost/in-cluster (milliseconds) or it isn't there at all —
# a long timeout only delays the fallback.
_CONNECT_TIMEOUT_SECONDS = 2.0

_client: Any = None
_unavailable = False


async def get_redis() -> Any | None:
    """Returns a shared Redis client, or None if Redis isn't reachable."""
    global _client, _unavailable

    if _unavailable:
        return None
    if _client is not None:
        return _client

    try:
        from redis.asyncio import Redis

        client = Redis.from_url(
            get_settings().redis_url,
            socket_connect_timeout=_CONNECT_TIMEOUT_SECONDS,
            socket_timeout=_CONNECT_TIMEOUT_SECONDS,
        )
        await asyncio.wait_for(client.ping(), timeout=_CONNECT_TIMEOUT_SECONDS)
        _client = client
        logger.info("REDIS connected url=%s", get_settings().redis_url)
        return _client
    except Exception as exc:  # noqa: BLE001 - any failure means "use the fallback"
        _unavailable = True
        logger.warning("REDIS unavailable (%s) — using in-process fallbacks.", exc)
        return None


async def close_redis() -> None:
    """Closes the shared client on API shutdown so connections aren't leaked."""
    global _client, _unavailable
    if _client is not None:
        try:
            await _client.aclose()
        except Exception:  # noqa: BLE001 - shutdown must never raise
            logger.debug("REDIS client close failed", exc_info=True)
        _client = None
    _unavailable = False
