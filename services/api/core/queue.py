"""Durable background-job queue (arq/Redis) with an in-process fallback.

Why this exists
---------------
Every long-running pipeline in this codebase (candidate ingestion, job matching,
assessment grading, pitch-deck analysis, hackathon ranking finalization) was scheduled
with FastAPI's `BackgroundTasks`. That has three properties that made the app feel broken
rather than merely slow:

1. Tasks run on the API process's own event loop, so CPU-bound work (sentence-transformer
   encoding) and blocking SDK calls stalled *every other in-flight request* across all
   five roles.
2. Tasks live only in memory. An API restart, deploy, or crash silently drops them, and
   the row they were supposed to finish stays `"processing"` forever — the user sees a
   spinner that never resolves and has no way to retry.
3. There is no retry. One transient GitHub/LLM/Qdrant blip permanently fails the job.

This module routes that work to an arq worker process instead (`services/workers/runner.py`),
which fixes all three: work runs off the API process entirely, survives restarts because
it lives in Redis, and retries with backoff.

Degrading gracefully
--------------------
Redis is genuinely optional. `enqueue()` falls back to the caller-supplied
`BackgroundTasks` whenever the queue is disabled by config, the Redis pool can't be
reached, or the enqueue itself fails. That keeps `docker compose` down / local dev / the
demo working exactly as before with no new required infrastructure — the queue is an
upgrade, not a dependency. Callers get a `bool` telling them which path ran, so status
semantics stay honest.

Idempotency
-----------
Enqueues pass an explicit `_job_id` derived from the task and its subject
(`"match:{job_id}"`). arq deduplicates on job id, so a double-clicked "Recompute" button
or a retried HTTP request coalesces into one run instead of two concurrent pipelines
racing to write the same rows.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import BackgroundTasks

from services.api.core.config import get_settings

logger = logging.getLogger(__name__)

# Task names. These are the string keys arq matches against the worker's registered
# function list, so they must stay in sync with `services/workers/tasks.py::TASKS`.
TASK_RUN_INGESTION = "task_run_ingestion"
TASK_RUN_MATCHING = "task_run_matching"
TASK_GRADE_SUBMISSION = "task_grade_submission"
TASK_ANALYZE_PRESENTATION = "task_analyze_presentation"
TASK_FINALIZE_RANKINGS = "task_finalize_rankings"

# Ceiling on the one-and-only connection probe. Redis is either up on localhost/in-cluster
# (milliseconds) or it isn't there at all — a long timeout only delays the fallback.
_CONNECT_TIMEOUT_SECONDS = 2.0

_pool: Any = None
_pool_unavailable = False


async def get_queue_pool() -> Any | None:
    """Returns a shared arq Redis pool, or None if the queue isn't usable.

    Cached process-wide: `create_pool` opens a connection pool, and building one per
    enqueue would repeat the exact mistake `get_llm_client` used to make. After a failed
    connection attempt this latches off (`_pool_unavailable`) so a down Redis costs one
    timeout per process rather than one per request — the fallback path is what runs.
    """
    global _pool, _pool_unavailable

    settings = get_settings()
    if not settings.queue_enabled or _pool_unavailable:
        return None
    if _pool is not None:
        return _pool

    try:
        from arq import create_pool
        from arq.connections import RedisSettings

        redis_settings = RedisSettings.from_dsn(settings.redis_url)
        # arq's default is 5 retries with its own backoff, which means a *down* Redis
        # costs ~30s before the first request gives up and falls back. The fallback is a
        # normal, supported mode here (no Redis in local dev), so probe once and fail
        # fast — the caller still gets its work done in-process.
        redis_settings.conn_retries = 0
        redis_settings.conn_timeout = _CONNECT_TIMEOUT_SECONDS

        _pool = await asyncio.wait_for(
            create_pool(redis_settings), timeout=_CONNECT_TIMEOUT_SECONDS
        )
        logger.info("QUEUE connected redis=%s", settings.redis_url)
        return _pool
    except Exception as exc:  # noqa: BLE001 - any failure means "use the fallback"
        _pool_unavailable = True
        logger.warning(
            "QUEUE unavailable (%s) — falling back to in-process BackgroundTasks. "
            "Long jobs will not survive an API restart.",
            exc,
        )
        return None


async def worker_is_alive(pool: Any) -> bool:
    """True when an arq worker has recently published its health key.

    Redis being reachable only means jobs can be *stored*; it says nothing about whether
    anything is consuming them. With `uvicorn` running but no
    `python -m services.workers.runner`, every enqueue used to succeed and the job would
    sit in Redis forever — the subject row stuck at "processing" and the UI polling until
    it timed out, with no error anywhere. That is a worse failure than not having a queue
    at all, because it is silent.

    arq's worker refreshes `arq:queue:health-check` on an interval and sets a TTL on it,
    so the key's presence is a live-worker signal rather than a stale flag left behind by
    a crashed process.

    Failures here answer "no": the caller then runs the job in-process, which is always
    safe. Never let a health probe be the thing that stops work from happening.
    """
    try:
        from arq.constants import default_queue_name, health_check_key_suffix

        return bool(await pool.exists(default_queue_name + health_check_key_suffix))
    except Exception:  # noqa: BLE001 - unknown health means "assume no worker"
        logger.debug("QUEUE worker health probe failed", exc_info=True)
        return False


async def close_queue_pool() -> None:
    """Closes the shared pool on API shutdown so Redis connections aren't leaked."""
    global _pool, _pool_unavailable
    if _pool is not None:
        try:
            await _pool.aclose()
        except Exception:  # noqa: BLE001 - shutdown must never raise
            logger.debug("QUEUE pool close failed", exc_info=True)
        _pool = None
    _pool_unavailable = False


async def enqueue(
    task_name: str,
    *args: Any,
    background_tasks: BackgroundTasks | None = None,
    fallback: Any = None,
    job_id: str | None = None,
) -> bool:
    """Enqueues `task_name` on the worker queue; returns True if it was truly queued.

    `fallback` is the in-process coroutine function to hand to `background_tasks` when the
    queue isn't available — it receives the same `*args`, so both paths execute identical
    work and there is only one implementation to keep correct.

    Returning False is not an error: it means the job is running in-process instead, and
    the caller's row/status semantics are unchanged.
    """
    pool = await get_queue_pool()
    if pool is not None and not await worker_is_alive(pool):
        # Redis is up but nothing is consuming the queue. Queueing here would strand the
        # job and leave the subject row at "processing" indefinitely, so run it in-process
        # instead — degraded (no durability, no retries) but the user's work completes.
        logger.warning(
            "QUEUE no live worker for task=%s — running in-process. "
            "Start `python -m services.workers.runner` for durable execution and retries.",
            task_name,
        )
        pool = None

    if pool is not None:
        try:
            settings = get_settings()
            await pool.enqueue_job(
                task_name,
                *args,
                _job_id=job_id,
                _expires=settings.queue_job_timeout_seconds * 2,
            )
            logger.info("QUEUE enqueued task=%s job_id=%s", task_name, job_id)
            return True
        except Exception:  # noqa: BLE001 - fall through to in-process execution
            logger.warning("QUEUE enqueue failed task=%s — running in-process", task_name, exc_info=True)

    if fallback is not None and background_tasks is not None:
        background_tasks.add_task(fallback, *args)
    elif fallback is not None:
        logger.error(
            "QUEUE task=%s had no BackgroundTasks to fall back to — job dropped", task_name
        )
    return False
