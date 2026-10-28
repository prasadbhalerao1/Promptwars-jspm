import asyncio
import logging
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from services.api.common.exceptions import APIException
from services.api.core.config import get_settings
from services.api.core.event_consumer import run_polling_loop
from services.api.core.rate_limit import RateLimitMiddleware
from services.api.modules import (
    admin,
    assessments,
    candidates,
    fraud,
    hackathons,
    presentations,
    public,
    recruitment,
    supervisor,
    users,
)

logger = logging.getLogger(__name__)

settings = get_settings()

# Sentry — Platform Hardening & Observability track (2026-07-30). Gated on a non-empty
# DSN so local dev (the current real state — SENTRY_DSN is empty in .env) never errors
# or sends anything. Pairs with the exception handler below: an unhandled exception is
# both logged locally and reported to Sentry when configured. See .agents/decisions.md's
# dated entry for exactly what a future session needs to supply to verify this live.
if settings.sentry_dsn and settings.sentry_dsn.strip().lower() not in {"", "changeme", "placeholder"}:
    sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1, send_default_pii=False)
    logger.info("Sentry error reporting enabled")
else:
    logger.info("SENTRY_DSN not configured — Sentry error reporting disabled")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown wiring.

    Replaces the three `@app.on_event` handlers this used to carry. `on_event` is
    deprecated in current FastAPI/Starlette and is slated for removal, so the app would
    eventually have started without its event consumer, without a warm embedder, and
    without ever closing the queue's Redis pool — silently, since a removed decorator
    does not error, it just never fires.

    Both startup tasks are deliberately fire-and-forget: neither may delay the app
    becoming ready, and both already handle their own failures.
    """
    # Fixed-interval polling background task — see services/api/core/event_consumer.py's
    # module docstring and .agents/decisions.md's 2026-07-30 entry for why a plain
    # asyncio loop was chosen over adding a Celery/Arq dependency for this one job.
    consumer_task = asyncio.create_task(run_polling_loop())
    # Pre-load the sentence-transformer model so the first career-guidance request
    # doesn't timeout waiting for model download/initialization (can take 30+ seconds
    # depending on network speed). Loaded lazily in background; subsequent requests
    # benefit from the cached model without blocking startup.
    embedder_task = asyncio.create_task(_load_embedder_async())

    yield

    consumer_task.cancel()
    embedder_task.cancel()
    # Releases the Redis client opened lazily by services/api/core/redis_client.py.
    from services.api.core.redis_client import close_redis

    await close_redis()


app = FastAPI(title="AI Talent Platform API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_allowed_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Rate limiting — Platform Hardening & Observability track (2026-07-30). Simple in-memory
# fixed-window limiter (services/api/core/rate_limit.py); see that module's docstring for
# why no Redis/slowapi dependency was added for this hackathon-demo-scale need. Added
# after CORSMiddleware so a 429 response still gets CORS headers (Starlette applies
# middleware in reverse of add order, so CORS — added first — ends up outermost).
app.add_middleware(RateLimitMiddleware)

app.include_router(users.router)
app.include_router(candidates.router)
app.include_router(presentations.router)
app.include_router(public.router)
app.include_router(recruitment.router)
app.include_router(assessments.router)
app.include_router(hackathons.router)
app.include_router(fraud.router)
app.include_router(supervisor.router)
app.include_router(admin.router)


from services.api.core.llm import (
    LLMNotConfigured,
    LLMQuotaExhausted,
    LLMRateLimited,
    LLMTimeout,
    LLMUnavailable,
)

# Maps each LLM failure to the status and code the client should act on. Everything used
# to collapse into one 503 "AI Engine Temporarily Unavailable", which told the UI to
# retry — wrong for three of these five: an exhausted quota and a missing API key do not
# resolve by waiting, and retrying them burns the user's time on a guaranteed failure.
#
# `retryable` drives the frontend's decision to back off and retry versus surface the
# error immediately, so it is part of the response rather than something the client
# infers from a status code.
_LLM_ERROR_RESPONSES: dict[type, tuple[int, str, str, bool]] = {
    LLMQuotaExhausted: (
        402,
        "LLM_QUOTA_EXHAUSTED",
        "The AI provider account is out of credit. This will not resolve on its own — "
        "an administrator needs to top up the account.",
        False,
    ),
    LLMNotConfigured: (
        503,
        "LLM_NOT_CONFIGURED",
        "The AI provider is not configured on this deployment. An administrator needs to "
        "set a valid API key.",
        False,
    ),
    LLMRateLimited: (
        429,
        "LLM_RATE_LIMITED",
        "The AI provider is rate limiting requests. Please try again shortly.",
        True,
    ),
    LLMTimeout: (
        504,
        "LLM_TIMEOUT",
        "The AI request took too long to complete. Please try again.",
        True,
    ),
}

_LLM_DEFAULT_RESPONSE = (
    503,
    "LLM_UNAVAILABLE",
    "The AI engine is temporarily unavailable. Please try again.",
    True,
)


@app.exception_handler(LLMUnavailable)
async def llm_unavailable_handler(request: Request, exc: LLMUnavailable) -> JSONResponse:
    # Exact type first, then walk the MRO, so a future subclass inherits its parent's
    # treatment rather than silently falling through to the retryable default.
    status_code, code, message, retryable = _LLM_DEFAULT_RESPONSE
    for cls in type(exc).__mro__:
        if cls in _LLM_ERROR_RESPONSES:
            status_code, code, message, retryable = _LLM_ERROR_RESPONSES[cls]
            break

    log = logger.error if not retryable else logger.warning
    log("LLM %s on %s %s: %s", code, request.method, request.url.path, str(exc))

    return JSONResponse(
        status_code=status_code,
        content={
            "detail": message,
            "code": code,
            "retryable": retryable,
        },
    )


@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": exc.message, "detail": exc.detail},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    sentry_sdk.capture_exception(exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error occurred. Please try again or check server logs."},
    )


async def _load_embedder_async() -> None:
    try:
        from services.agents.recruitment.tools.embeddings import get_embedder

        # `get_embedder()` loads the model from disk — seconds of pure CPU/IO. Awaiting
        # it via to_thread keeps it off the event loop; calling it directly here (as this
        # did before) blocked every request for the duration of the very startup work
        # that was supposed to happen in the background.
        await asyncio.to_thread(get_embedder)
        logger.info("Embedder model pre-loaded successfully")
    except Exception as exc:
        logger.warning("Failed to pre-load embedder model: %s", exc)


@app.get("/health")
def health():
    return {"status": "ok"}
