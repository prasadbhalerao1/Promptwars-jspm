"""Re-ranking Agent — FR-3.3. Node contract: constraints.md §2.3. Sonnet, only over the
bounded `shortlist` from `hybrid_search` (doc 02 §2's cost bound)."""

from services.agents.recruitment.state import CopilotState
from services.agents.recruitment.tools.copilot_llm import rerank_candidates


async def run(state: CopilotState) -> dict:
    shortlist = state.get("shortlist") or []
    if not shortlist:
        return {"ranked_candidate_ids": []}

    payload = [
        {
            "candidate_id": c["candidate_id"],
            "headline": c.get("headline"),
            "location": c.get("location"),
            "skills": [s["name"] for s in c.get("skills", [])],
            "overall_talent_score": c.get("overall_talent_score"),
            "hackathon_experience": c.get("hackathon_experience"),
            "repo_summaries": c.get("repo_summaries", []),
        }
        for c in shortlist
    ]
    ordered_ids = await rerank_candidates(state["raw_query"], payload)

    # Defensive: the model is instructed not to add/omit ids, but never trust that blindly
    # — fall back to the pre-rerank order for anything it dropped, and drop anything it
    # invented that wasn't actually in the shortlist.
    valid_ids = {c["candidate_id"] for c in shortlist}
    ranked = [cid for cid in ordered_ids if cid in valid_ids]
    missing = [c["candidate_id"] for c in shortlist if c["candidate_id"] not in ranked]
    return {"ranked_candidate_ids": ranked + missing}
