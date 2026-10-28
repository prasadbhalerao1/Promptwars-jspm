"""Explanation Agent — FR-3.3. Node contract: constraints.md §2.3. Haiku, must cite
specific evidence fields, never invent (same grounding guardrail as Module 01's
fact-check agent)."""

from services.agents.recruitment.state import CopilotState
from services.agents.recruitment.tools.copilot_llm import explain_matches

# Only explain the top N — an explanation for candidate #47 in a shortlist the recruiter
# will likely never scroll to isn't worth the token cost.
_EXPLAIN_TOP_N = 10


async def run(state: CopilotState) -> dict:
    ranked_ids = state.get("ranked_candidate_ids") or []
    if not ranked_ids:
        return {"explanations": {}}

    by_id = {c["candidate_id"]: c for c in state.get("shortlist") or []}
    top = [by_id[cid] for cid in ranked_ids[:_EXPLAIN_TOP_N] if cid in by_id]

    payload = [
        {
            "candidate_id": c["candidate_id"],
            "skills": [s["name"] for s in c.get("skills", [])],
            "overall_talent_score": c.get("overall_talent_score"),
            "hackathon_experience": c.get("hackathon_experience"),
            "repo_summaries": c.get("repo_summaries", []),
            "github_username": c.get("github_username"),
        }
        for c in top
    ]
    explanations = await explain_matches(state["raw_query"], payload)
    return {"explanations": explanations}
