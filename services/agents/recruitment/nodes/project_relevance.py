"""Project Relevance Agent — FR-2.3, "rules + embedding" per the agent registry. Node
contract: constraints.md §2.3. Queries `candidate_project_embeddings` (reused from Module
01) filtered per-candidate against the job vector, in one batched Qdrant round-trip for
the whole candidate pool rather than one sequential `.search()` call per candidate."""

import asyncio

from services.agents.recruitment.state import MatchingState
from services.agents.recruitment.tools.embeddings import batch_candidate_project_relevance, get_qdrant_client


async def run(state: MatchingState) -> dict:
    """Async wrapper only — `search_batch` is a blocking Qdrant network call, so it runs
    off the event loop (see `match_candidates.run`)."""
    return await asyncio.to_thread(_run_sync, state)


def _run_sync(state: MatchingState) -> dict:
    client = get_qdrant_client()
    job_vector = state["job_embedding"]
    candidate_ids = [c["candidate_id"] for c in state.get("candidate_pool") or []]

    scores = batch_candidate_project_relevance(client, candidate_ids, job_vector)
    return {"project_relevance_scores": scores}
