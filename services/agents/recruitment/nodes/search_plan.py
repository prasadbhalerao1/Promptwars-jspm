"""Search Plan Agent — FR-3.2. Node contract: constraints.md §2.3.

Per doc/multi-agent-architecture/02 §4 this is a Haiku-tier "Agent," but the decision it
makes (which of `structured_filters`' fields are hard/structured vs which residual text
needs semantic search) is entirely mechanical given `query_understanding`'s already-typed
output — no natural-language judgment is actually required here. The same agent registry
table already has several "Agent"-named nodes that are rules-only (Matching Agent, Score
Aggregation Agent), so this follows that precedent rather than adding an LLM call with
nothing for it to decide. `hybrid_search` executes the plan this node produces.

This deployment fetches the whole `candidate_pool` in one query (`hybrid_search` filters
it in Python) rather than issuing separate Postgres-WHERE and Qdrant-payload-filter
queries against two different stores — a reasonable simplification for the pool sizes
this system runs at, not a literal Postgres-vs-Qdrant split. `search_plan`'s output still
records which fields are "hard filters" vs "semantic" so that split is explicit and easy
to re-target at real separate queries later if the candidate pool grows past what a single
fetch can hold.
"""

from services.agents.recruitment.state import CopilotState


async def run(state: CopilotState) -> dict:
    filters = state["structured_filters"]
    hard_filters = {
        k: v
        for k, v in {
            "location": filters.get("location"),
            "skills": filters.get("skills") or None,
            "min_talent_score": filters.get("min_talent_score"),
            "hackathon_experience": filters.get("hackathon_experience"),
            "remote_ok": filters.get("remote_ok"),
        }.items()
        if v is not None
    }
    return {
        "structured_filters": {
            **filters,
            "_hard_filters": hard_filters,
        }
    }
