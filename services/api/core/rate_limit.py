"""Fixed-window rate-limit middleware, Redis-backed with an in-memory fallback.

Counters live in Redis when it is reachable, so the limit is enforced across every API
process. The original implementation was purely in-process, which meant the effective
limit was `RATE_LIMIT_PER_MINUTE x number_of_workers` — running uvicorn with 4 workers
silently quadrupled it — and every counter reset on restart. The shared client lives in
`services/api/core/redis_client.py`.

When Redis is unavailable the middleware degrades to the in-process counter rather than
failing open or rejecting traffic: a rate limiter that 500s is worse than one that is
merely per-process. The fallback is bounded (see `_MAX_TRACKED_BUCKETS`) — the previous
`defaultdict` grew forever, one permanent entry per distinct client IP, which is a slow
memory leak on any internet-facing deployment.

Keyed by authenticated user id when a bearer token is present (best-effort, never raises
— this middleware must not become a second, competing auth gate; `rbac.py`'s
`get_current_user` dependency remains the single source of truth for authorization),
falling back to client IP for unauthenticated requests. `/health` is exempt so uptime
checks never 429.
"""

from __future__ import annotations

import logging
import time

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from services.api.core.config import get_settings

logger = logging.getLogger(__name__)

_EXEMPT_PATHS = {"/health"}

# Ceiling on distinct buckets held in the in-memory fallback. Well above any realistic
# number of concurrent clients for this deployment, but bounded so a burst of unique
# source IPs cannot grow the dict without limit.
_MAX_TRACKED_BUCKETS = 10_000


def _decode_user_id_best_effort(authorization: str | None) -> str | None:
    """Pull the subject claim out of a custom bearer JWT without verifying it.

    This is a rate-limit *bucket key*, not an authorization decision — using the
    unverified subject claim just means two different rate-limit buckets in the
    pathological case of a forged token, never a security gap, since `rbac.py`'s real
    verified `get_current_user` dependency still runs afterwards and still rejects a
    forged/expired token as normal. Avoids re-running full JWT verification twice per
    request purely to pick a bucket key.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        import base64
        import json

        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        sub = payload.get("sub")
        return str(sub) if sub else None
    except Exception:
        return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window rate limiter: `RATE_LIMIT_PER_MINUTE` requests per 60s window per
    bucket key (user id, else client IP). Returns 429 with
    `{"detail": "rate_limit_exceeded"}` on overflow — never raises, never blocks
    `/health`.
    """

    _WINDOW_SECONDS = 60

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._settings = get_settings()
        # Fallback only, used when Redis is unreachable.
        # bucket_key -> (window_start_monotonic, count_in_window)
        self._buckets: dict[str, tuple[float, int]] = {}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        # CORS preflights carry no Authorization header, so they cannot be attributed to
        # a user and fall through to the shared client-IP bucket. The browser issues one
        # per cross-origin request, so counting them meant a page's real requests
        # competed with their own preflights for the same allowance — and every user
        # behind one NAT'd address shared it. They reach no application code, so there is
        # nothing here worth rationing.
        if request.method == "OPTIONS":
            return await call_next(request)

        limit = self._settings.rate_limit_per_minute
        if limit <= 0:
            # 0 or negative means "no limit" — an explicit opt-out, not a footgun.
            return await call_next(request)

        bucket_key = _decode_user_id_best_effort(request.headers.get("authorization"))
        if bucket_key is None:
            client = request.client
            bucket_key = client.host if client else "unknown"

        count = await self._incr_redis(bucket_key)
        if count is None:
            count = self._incr_local(bucket_key)

        if count > limit:
            return JSONResponse(status_code=429, content={"detail": "rate_limit_exceeded"})

        return await call_next(request)

    async def _incr_redis(self, bucket_key: str) -> int | None:
        """Increments the shared counter; returns the new count, or None if unavailable.

        The window is encoded in the key (`…:<window_number>`) rather than tracked as a
        stored timestamp, so window rollover needs no read-modify-write and no cleanup —
        the old key simply stops being addressed and expires on its own. INCR and EXPIRE
        are pipelined so a request costs one round trip, and INCR is atomic, so
        concurrent requests in the same window cannot lose counts to a race the way a
        get-then-set would.
        """
        try:
            from services.api.core.redis_client import get_redis

            pool = await get_redis()
            if pool is None:
                return None

            window = int(time.time()) // self._WINDOW_SECONDS
            key = f"ratelimit:{bucket_key}:{window}"
            pipe = pool.pipeline()
            pipe.incr(key)
            # Slightly beyond the window so a counter can never outlive its own window
            # yet is always reclaimed.
            pipe.expire(key, self._WINDOW_SECONDS + 10)
            count, _ = await pipe.execute()
            return int(count)
        except Exception:  # noqa: BLE001 - rate limiting must never break the request path
            logger.debug("Redis rate-limit check failed; using in-process fallback", exc_info=True)
            return None

    def _incr_local(self, bucket_key: str) -> int:
        """Per-process fixed-window counter used when Redis is unreachable."""
        now = time.monotonic()
        window_start, count = self._buckets.get(bucket_key, (0.0, 0))
        if now - window_start >= self._WINDOW_SECONDS:
            window_start, count = now, 0
        count += 1

        if bucket_key not in self._buckets and len(self._buckets) >= _MAX_TRACKED_BUCKETS:
            # At capacity with a new key: drop entries whose window has already rolled
            # over. They are dead weight — a lookup would reset them anyway.
            self._buckets = {
                k: v for k, v in self._buckets.items() if now - v[0] < self._WINDOW_SECONDS
            }
            if len(self._buckets) >= _MAX_TRACKED_BUCKETS:
                # Every tracked bucket is still live. Admit the request rather than
                # tracking it: under this much pressure the shared Redis counter is the
                # real defence, and silently 429ing an unknown client because a dict is
                # full would be a worse failure than briefly under-counting.
                return 1

        self._buckets[bucket_key] = (window_start, count)
        return count
