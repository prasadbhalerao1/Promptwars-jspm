"""Matching Agent — FR-2.1/2.2, "rules + embedding similarity, no LLM needed for the
numeric score itself" per the agent registry. Node contract: constraints.md §2.3.

Computes the three non-project terms (SkillOverlap, SemanticSimilarity, ExperienceMatch,
TalentScoreAlignment) for every candidate in the pool. Fans out to both
`project_relevance` and `score_aggregation` directly (doc 02 §3's mermaid: MATCH -> PROJ,
MATCH -> AGG) — writes only `core_match_scores`, a key `project_relevance` never touches,
so no reducer is needed for the fan-out (same no-collision reasoning as
candidate_intelligence's `CareerGuidanceState`)."""

import asyncio

from services.agents.recruitment.state import MatchingState
from services.agents.recruitment.tools.embeddings import (
    candidate_skill_centroid,
    cosine_similarity,
    embed_skills,
)
from services.agents.recruitment.tools.matching import (
    CandidateSkillSignal,
    experience_match,
    filter_match_ratio,
    semantic_similarity,
    skill_overlap,
    talent_score_alignment,
)


async def run(state: MatchingState) -> dict:
    """Async wrapper only — the real work is CPU-bound (sentence-transformer encoding plus
    a per-candidate scoring loop) and runs off the event loop via `asyncio.to_thread`.

    Matching executes as a FastAPI BackgroundTask, which shares the API process's event
    loop. Running this inline blocked that loop for the entire matching run, so every
    other in-flight request across all five roles stalled behind one recruiter's job
    creation — a large part of why the app felt globally slow rather than slow in one
    place. Same pattern as `github_analysis.py` and `core/llm.py`.
    """
    return await asyncio.to_thread(_run_sync, state)


def _run_sync(state: MatchingState) -> dict:
    job_vector = state["job_embedding"]
    required_skills = state.get("job_required_skills") or []
    job_location = state.get("job_location")
    job_is_remote = state.get("job_is_remote", True)
    min_experience = state.get("job_min_experience_years")

    pool = state.get("candidate_pool") or []

    # Warm the skill-vector cache for the whole pool in ONE batched encode before the
    # per-candidate loop below. Everything downstream (candidate_skill_centroid,
    # skill_overlap's and talent_score_alignment's best_skill_similarity fallbacks) then
    # reads from cache instead of re-encoding. Without this, a single matching run cost
    # O(candidates x required_skills x skills_per_candidate) model invocations over a set
    # of only O(distinct skills) unique strings — by far the dominant cost of matching.
    distinct_skills = {
        s["name"] for candidate in pool for s in candidate.get("skills", []) if s.get("name")
    }
    distinct_skills.update(required_skills)
    if distinct_skills:
        embed_skills(sorted(distinct_skills))

    core_scores: dict[str, dict] = {}
    for candidate in pool:
        cid = candidate["candidate_id"]
        skill_signals = [
            CandidateSkillSignal(name=s["name"], verified=s.get("verified", False))
            for s in candidate.get("skills", [])
        ]
        skill_names = [s.name for s in skill_signals]
        centroid = candidate_skill_centroid(skill_names)
        cos = cosine_similarity(job_vector, centroid) if centroid else 0.0
        fmr = filter_match_ratio(candidate.get("location"), job_location, job_is_remote)

        talent_adjusted, talent_metadata = talent_score_alignment(
            candidate_overall_talent_score=candidate.get("overall_talent_score"),
            candidate_sub_scores={
                "coding_ability": candidate.get("sub_scores", {}).get("coding_ability"),
                "problem_solving": candidate.get("sub_scores", {}).get("problem_solving"),
                "project_quality": candidate.get("sub_scores", {}).get("project_quality"),
                "innovation": candidate.get("sub_scores", {}).get("innovation"),
                "technical_consistency": candidate.get("sub_scores", {}).get("technical_consistency"),
                "community_participation": candidate.get("sub_scores", {}).get("community_participation"),
                "leadership": candidate.get("sub_scores", {}).get("leadership"),
                "open_source_contributions": candidate.get("sub_scores", {}).get("open_source_contributions"),
                "hackathon_performance": candidate.get("sub_scores", {}).get("hackathon_performance"),
            },
            candidate_skills=skill_signals,
            required_skills=required_skills,
        )

        core_scores[cid] = {
            "skill_similarity": skill_overlap(skill_signals, required_skills),
            "semantic_similarity": semantic_similarity(cos, fmr),
            "experience_match": experience_match(candidate.get("experience_years"), min_experience),
            "talent_score_alignment": talent_adjusted,
            "talent_score_metadata": talent_metadata,
        }

    return {"core_match_scores": core_scores}
