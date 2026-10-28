"""Job Embedding Agent — FR-2.2. Node contract: constraints.md §2.3. Embeds the job
description + required skills once per posting, upserts into `job_description_embeddings`
(doc 02 §6)."""

import asyncio

from services.agents.recruitment.state import MatchingState
from services.agents.recruitment.tools.embeddings import (
    embed_texts,
    get_qdrant_client,
    upsert_job_embedding,
)


async def run(state: MatchingState) -> dict:
    """Async wrapper only — embedding is CPU-bound and the Qdrant upsert is a blocking
    network call, so both go off the event loop (see `match_candidates.run`)."""
    return await asyncio.to_thread(_run_sync, state)


def _run_sync(state: MatchingState) -> dict:
    text = state["job_description"] + "\n\nRequired skills: " + ", ".join(state.get("job_required_skills") or [])
    job_vector = embed_texts([text])[0]

    client = get_qdrant_client()
    upsert_job_embedding(
        client,
        job_id=state["job_id"],
        job_vector=job_vector,
        location=state.get("job_location"),
        remote_ok=state.get("job_is_remote", True),
        required_skill_tags=state.get("job_required_skills") or [],
    )
    return {"job_embedding": job_vector}
