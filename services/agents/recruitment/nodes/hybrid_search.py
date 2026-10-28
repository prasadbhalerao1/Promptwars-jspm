"""Hybrid Search execution — FR-3.2/3.3, "tool call, no LLM" per the agent registry. Node
contract: constraints.md §2.3.

Applies `search_plan`'s hard filters to the pre-fetched `candidate_pool` (deterministic,
zero-cost step per doc 02 §2), then — only if there's residual `semantic_query` text —
ranks the survivors by embedding similarity via `embeddings.candidate_skill_centroid`, the
same centroid technique Module 01 uses for role matching. Bounds the output to the top ~50
candidates, which is what keeps the downstream Sonnet re-rank cost-bounded (doc 02 §2's
"LLM only on the final shortlist" rule).
"""

import asyncio

from services.agents.recruitment.state import CopilotState
from services.api.core.config import get_settings
from services.agents.recruitment.tools.embeddings import (
    SKILL_SIMILARITY_THRESHOLD,
    candidate_skill_centroid,
    cosine_similarity,
    embed_skills,
    embed_texts,
)

_SHORTLIST_LIMIT = get_settings().recruitment_shortlist_limit


def _skill_matches(
    candidate_skill_names: list[str],
    candidate_vectors: list[list[float]] | None,
    required_skills: list[str],
    required_vectors_by_name: dict[str, list[float]],
) -> bool:
    """A candidate satisfies a required skill if they have it literally (case-insensitive),
    or if their skill list contains something embedding-similar (e.g. "Vue.js" against a
    required "React") — previously this was pure exact-match, so a candidate with only
    closely related skills was excluded from the shortlist before the semantic ranking
    step below ever got a chance to see them, even though the ranking step already uses
    real embeddings for the free-text query. Both `required_vectors_by_name` and
    `candidate_vectors` are precomputed once per search/candidate (not once per
    (candidate, skill) pair) to keep this an O(candidates + required_skills) number of
    embedding calls, not O(candidates * required_skills)."""
    candidate_by_lower = {name.lower() for name in candidate_skill_names}

    for skill in required_skills:
        if skill.lower() in candidate_by_lower:
            continue
        if not candidate_vectors:
            return False
        required_vector = required_vectors_by_name[skill]
        best_similarity = max(
            (cosine_similarity(required_vector, v) for v in candidate_vectors),
            default=0.0,
        )
        if best_similarity < SKILL_SIMILARITY_THRESHOLD:
            return False
    return True


def _matches_hard_filters(
    candidate: dict,
    hard_filters: dict,
    required_vectors_by_name: dict[str, list[float]],
    candidate_vectors_by_id: dict[str, list[list[float]] | None],
) -> bool:
    if "location" in hard_filters:
        if (candidate.get("location") or "").strip().lower() != hard_filters["location"].strip().lower():
            return False
    if "skills" in hard_filters:
        candidate_skill_names = [s["name"] for s in candidate.get("skills", [])]
        candidate_vectors = candidate_vectors_by_id.get(candidate["candidate_id"])
        if not _skill_matches(candidate_skill_names, candidate_vectors, hard_filters["skills"], required_vectors_by_name):
            return False
    if "min_talent_score" in hard_filters:
        score = candidate.get("overall_talent_score")
        if score is None or score < hard_filters["min_talent_score"]:
            return False
    if "hackathon_experience" in hard_filters and hard_filters["hackathon_experience"]:
        if not candidate.get("hackathon_experience"):
            return False
    return True


async def run(state: CopilotState) -> dict:
    """Async wrapper only — see `_run_sync`. Embedding + filtering is CPU-bound and this
    node runs directly on the Copilot request path, so keep it off the event loop."""
    return await asyncio.to_thread(_run_sync, state)


def _run_sync(state: CopilotState) -> dict:
    filters = state["structured_filters"]
    hard_filters = filters.get("_hard_filters", {})
    pool = state.get("candidate_pool") or []

    # Only pay for embeddings when a "skills" hard filter is actually present — most
    # Copilot queries filter on location/talent-score/hackathon-experience alone, and
    # those stay free deterministic comparisons exactly as before.
    required_vectors_by_name: dict[str, list[float]] = {}
    candidate_vectors_by_id: dict[str, list[list[float]] | None] = {}
    required_skills = hard_filters.get("skills") or []
    if required_skills:
        # Compared via each skill's curated description (skill_descriptions.py), not the
        # bare name — bare short skill-name embeddings don't reliably separate genuinely
        # related skills from unrelated ones (measured directly; see
        # embeddings.SKILL_SIMILARITY_THRESHOLD's docstring).
        # `embed_skills` applies describe_skill() internally and memoizes per distinct
        # skill, so the repeated skills across the pool are encoded once, not once per
        # candidate.
        required_vectors = embed_skills(required_skills)
        required_vectors_by_name = dict(zip(required_skills, required_vectors))
        for candidate in pool:
            skill_names = [s["name"] for s in candidate.get("skills", [])]
            candidate_vectors_by_id[candidate["candidate_id"]] = (
                embed_skills(skill_names) if skill_names else None
            )

    survivors = [
        c for c in pool if _matches_hard_filters(c, hard_filters, required_vectors_by_name, candidate_vectors_by_id)
    ]

    semantic_query = filters.get("semantic_query", "").strip()
    if semantic_query and survivors:
        query_vector = embed_texts([semantic_query])[0]
        scored = []
        for candidate in survivors:
            skill_names = [s["name"] for s in candidate.get("skills", [])]
            centroid = candidate_skill_centroid(skill_names)
            similarity = max(0.0, cosine_similarity(query_vector, centroid)) if centroid else 0.0
            # Carried through to the response as a display "match_percentage" for
            # Copilot results — this is retrieval relevance, not the formal per-job
            # doc-08 4-term MatchScore (Copilot search isn't necessarily job-scoped).
            candidate = {**candidate, "_retrieval_score": round(100.0 * similarity, 1)}
            scored.append((similarity, candidate))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        shortlist = [c for _, c in scored[:_SHORTLIST_LIMIT]]
    else:
        # No residual semantic intent — structured filters already did all the work;
        # break ties by Talent Score so the shortlist still has a sensible order going
        # into re-ranking.
        survivors.sort(key=lambda c: c.get("overall_talent_score") or 0.0, reverse=True)
        shortlist = survivors[:_SHORTLIST_LIMIT]

    return {"shortlist": shortlist}
