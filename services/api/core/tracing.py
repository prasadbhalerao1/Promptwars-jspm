"""Langfuse tracing — Platform Hardening & Observability track (2026-07-30, live-wiring pass).

Two context managers, both no-ops when `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` are
empty or a placeholder (same "typed empty default, fails closed, never fabricates"
pattern used repo-wide for `ANTHROPIC_API_KEY`/`CLOUDINARY_URL`, doc/SRS Module 01 §9):

  1. `start_agent_trace(...)` — one per agent-graph run (one `graph.ainvoke()` call =
     one Langfuse trace). Router call sites open this right before invoking a graph and
     read `span.trace_id` afterward for `AgentRun.langfuse_trace_id`.
  2. `start_llm_generation(...)` — one per actual model call, used exclusively by
     `services.api.core.llm.generate_structured/generate_completion`. Never call this
     directly from agent tool code — go through `services.api.core.llm` so every model
     call is captured the same way regardless of provider.

Langfuse's OTel-based context propagation means a `start_llm_generation` opened deep
inside a `services/agents/*/graph.py` node function automatically nests under whichever
`start_agent_trace` span is active higher up the same `await` chain — no manual
plumbing of span objects through node functions is needed.
"""

from __future__ import annotations

import logging
import re
from contextlib import contextmanager
from functools import lru_cache
from typing import Any, Iterator

from services.api.core.config import get_settings

logger = logging.getLogger(__name__)

_PLACEHOLDER_VALUES = {"", "changeme", "placeholder", "your-key-here", "your-public-key", "your-secret-key"}

# Candidate resumes, interview transcripts, and cover letters routinely contain the
# candidate's own contact details in free text (e.g. "reach me at jane@x.com"). This is a
# floor on what leaves the process boundary to a third party (Langfuse Cloud) for
# observability.
_EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE_PATTERN = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")


def _redact_pii(value: str) -> str:
    redacted = _EMAIL_PATTERN.sub("[REDACTED_EMAIL]", value)
    return _PHONE_PATTERN.sub("[REDACTED_PHONE]", redacted)


def _mask_otel_spans(*, params: Any) -> Any:
    """`mask_otel_spans` hook (the SDK-recommended masking mechanism, not the legacy
    `mask` hook) — redacts email/phone patterns from every string span attribute in each
    export batch, right before it leaves the process for Langfuse Cloud."""
    from langfuse.types import MaskOtelSpansResult, OtelSpanPatch

    patches = {}
    for identifier, span in params.spans.items():
        replacements = {}
        for key, value in span.attributes.items():
            if isinstance(value, str):
                masked = _redact_pii(value)
                if masked != value:
                    replacements[key] = masked
        if replacements:
            patches[identifier] = OtelSpanPatch(set_attributes=replacements)
    return MaskOtelSpansResult(span_patches=patches)


def _is_placeholder(value: str) -> bool:
    return value.strip().lower() in _PLACEHOLDER_VALUES


@lru_cache
def _get_client() -> Any | None:
    """Return a cached Langfuse client, or `None` if tracing isn't configured.

    `lru_cache` means this is evaluated once per process, and a missing/placeholder key
    reliably short-circuits every call site below to a no-op for the lifetime of the
    process — no per-request settings re-check, no per-request crash risk.
    """
    settings = get_settings()
    if _is_placeholder(settings.langfuse_public_key) or _is_placeholder(settings.langfuse_secret_key):
        return None
    try:
        from langfuse import Langfuse
    except ImportError:
        logger.warning("langfuse package not installed; Langfuse tracing disabled")
        return None
    try:
        client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host or "https://cloud.langfuse.com",
            mask_otel_spans=_mask_otel_spans,
        )
        if not client.auth_check():
            logger.warning("Langfuse credentials rejected by server; tracing disabled")
            return None
        return client
    except Exception:
        # Tracing setup must never take the API down — degrade to the same "always None"
        # state this column has had since every module shipped.
        logger.exception("Failed to initialize Langfuse client; tracing disabled")
        return None


def is_tracing_enabled() -> bool:
    return _get_client() is not None


class _NullObservation:
    """Stand-in yielded by both context managers below when tracing is disabled, so
    callers never need an `if` around this — `.update(...)` is a no-op and `.trace_id`
    is `None`, exactly the value every `AgentRun.langfuse_trace_id` has always had."""

    trace_id: str | None = None

    def update(self, **_kwargs: Any) -> None:
        return None


@contextmanager
def start_agent_trace(
    name: str,
    input_data: Any = None,
    user_id: str | None = None,
    session_id: str | None = None,
    tags: list[str] | None = None,
) -> Iterator[Any]:
    """Root span for one agent-graph run. Use once per `graph.ainvoke()` call site:

        with start_agent_trace("candidate-intelligence-ingest", input_data=..., user_id=str(candidate_id)) as trace:
            result = await graph.ainvoke(initial_state)
            trace.update(output=output_summary)

        AgentRun(..., langfuse_trace_id=trace.trace_id)
    """
    client = _get_client()
    if client is None:
        yield _NullObservation()
        return

    from langfuse import propagate_attributes

    settings = get_settings()
    with propagate_attributes(
        user_id=user_id, session_id=session_id, tags=tags or [], environment=settings.environment
    ):
        with client.start_as_current_observation(as_type="span", name=name, input=input_data) as span:
            try:
                yield span
            finally:
                client.flush()


@contextmanager
def start_llm_generation(
    name: str,
    model: str,
    input_data: Any = None,
    metadata: dict[str, Any] | None = None,
) -> Iterator[Any]:
    """One `generation` observation per model call — only called from
    `services.api.core.llm`. Nests under the active `start_agent_trace` span
    automatically via OTel context propagation."""
    client = _get_client()
    if client is None:
        yield _NullObservation()
        return

    with client.start_as_current_observation(
        as_type="generation", name=name, model=model, input=input_data, metadata=metadata
    ) as generation:
        yield generation
