"""Cross-Event Novelty Agent — doc 05 §4: "Qdrant search across `presentation_slide_
embeddings` spanning *all* past hackathons, not just this one." Reuses that search
directly off Module 04's own already-computed output rather than re-embedding slide text
and re-querying Qdrant a second time: `plagiarism_matches` (`services/agents/ppt_analyzer/
tools/plagiarism.py`) is itself the result of exactly that cross-corpus Qdrant search,
run once at deck-upload time against the *entire* presentation corpus (not scoped to any
one hackathon) — so "has this idea appeared before" is already answered by whether this
team's presentation has any `plagiarism_matches` rows at all.

Rule-based (no LLM), consistent with the agent registry's "embedding similarity (tool) +
Haiku narrative" being narrative-optional per Module 04's own precedent (its plagiarism
node treats Haiku narrative as "optional UI-copy enhancement, not part of detection").

Router pre-fetches each team's `plagiarism_similarities` (the `similarity` column of every
`plagiarism_matches` row referencing that team's `presentation_id`) before invoking this
graph — this node stays DB-free like every other node in this codebase.
"""

from services.agents.hackathon.state import HackathonRankingState

# Same 0-100 scale as every other score in this system.
_NOVELTY_SCALE = 100.0


async def run(state: HackathonRankingState) -> dict:
    novelty_scores: dict[str, float | None] = {}

    for team in state["teams"]:
        team_id = team["team_id"]
        if not team.get("presentation_id"):
            # No deck linked at all — genuinely N/A, not "fully novel". Re-normalized
            # away by the Ranking Aggregation Agent, same as every other missing
            # component in this system.
            novelty_scores[team_id] = None
            continue

        similarities = team.get("plagiarism_similarities") or []
        if not similarities:
            novelty_scores[team_id] = _NOVELTY_SCALE
            continue

        max_similarity = max(similarities)
        novelty_scores[team_id] = round(_NOVELTY_SCALE * (1 - max_similarity), 2)

    return {"novelty_scores": novelty_scores}
