"""Qdrant client construction — shared by every module that does vector search (Job
Matching/Copilot, Talent Score innovation-novelty, Career Guidance skill-gap, PPT
Analyzer plagiarism/cross-event-novelty). Previously each module hand-rolled its own
"connect, verify with get_collections(), wrap the exception" logic; consolidated here
since all four copies were byte-for-byte identical except for how they signal failure.

Two failure conventions coexist across call sites and both are preserved exactly:
- Some callers (recruitment matching, skill-gap) want a hard failure — Qdrant being
  unreachable means the whole feature has no output, so a typed exception should
  propagate and become a 503, never a fabricated score.
- Others (innovation novelty, plagiarism) treat Qdrant as one optional signal among
  several — Qdrant being unreachable should cold-start-degrade (return `None`/skip),
  not take down the whole request.
`raise_on_unavailable` picks between the two without duplicating the connection logic.
"""

import logging
import threading

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from services.api.core.config import get_settings

logger = logging.getLogger(__name__)

# The connected client is a process-level singleton, for the same reason `get_embedder()`
# and `get_llm_client()` are. Every call used to build a fresh `QdrantClient` — a new
# httpx connection pool — and then immediately spend a round trip on `get_collections()`
# purely to prove reachability. On the matching path (`job_embed` then
# `project_relevance`) that was two throwaway pools and two wasted round trips per run.
#
# Reachability is therefore verified once, on first construction. A Qdrant that dies
# later surfaces as an error from the actual search call, which every caller already
# handles — the health-check probe never protected against that anyway, since Qdrant
# could always drop between the probe and the real query.
_client: QdrantClient | None = None
_client_lock = threading.Lock()


class QdrantUnavailable(RuntimeError):
    """Raised when Qdrant isn't reachable, if the caller asked to raise rather than
    receive `None` — never fabricate a vector-search result."""


def get_qdrant_client(*, raise_on_unavailable: bool = True) -> QdrantClient | None:
    global _client
    if _client is not None:
        return _client

    # Lock so that concurrent first-callers build one client rather than racing to build
    # several. Callers reach this from `asyncio.to_thread`, so this is genuinely
    # multi-threaded, not just conceptually.
    with _client_lock:
        if _client is not None:
            return _client
        settings = get_settings()
        try:
            # Use prefer_grpc=False to force HTTP/REST client (has search() method).
            # By default, QdrantClient tries gRPC first, which doesn't have search() in all versions.
            client = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key or None,
                timeout=get_settings().qdrant_timeout_seconds,
                prefer_grpc=False
            )
            client.get_collections()
            _client = client
            return _client
        except Exception as exc:
            # Deliberately not cached: unlike a missing API key, an unreachable Qdrant is
            # usually transient (container still starting), and latching the failure would
            # keep the feature dark until the API process restarted.
            if raise_on_unavailable:
                raise QdrantUnavailable(f"Qdrant is not reachable at {settings.qdrant_url}: {exc}") from exc
            return None


def ensure_payload_indexes(client: QdrantClient, collection: str, fields: dict[str, str]) -> None:
    """Creates keyword/other payload indexes for `fields` ({field_name: schema_type}).

    Without a payload index, a filtered vector search in Qdrant cannot use the HNSW graph
    for the filtered subset and degrades toward scanning the collection to evaluate the
    filter. Every filtered search in this codebase runs on an unindexed payload field
    today (`candidate_id` on project embeddings, `presentation_id` on slides, `role` on
    the skill taxonomy), so each one pays that scan — and the cost grows with total
    collection size rather than with the size of the matching subset. That is precisely
    the shape of "it was fast in dev and crawls once real data lands".

    Idempotent and best-effort: creating an index that already exists is a no-op error we
    swallow, and an index that can't be created is a performance regression, never a
    correctness one — the search still returns the same results, just slower. So this
    must never take down the calling feature.
    """
    for field_name, schema_type in fields.items():
        try:
            client.create_payload_index(
                collection_name=collection,
                field_name=field_name,
                field_schema=schema_type,
            )
        except Exception:  # noqa: BLE001 - already-exists and races are both benign
            logger.debug(
                "Payload index %s.%s not created (likely already present)",
                collection,
                field_name,
                exc_info=True,
            )


__all__ = ["QdrantUnavailable", "ensure_payload_indexes", "get_qdrant_client", "qmodels"]
