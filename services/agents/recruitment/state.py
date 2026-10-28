from typing import Optional, TypedDict


class CopilotState(TypedDict):
    """Flow A — Recruiter Copilot (doc/multi-agent-architecture/02 §3). One `ainvoke()`
    per turn — no LangGraph checkpointer (nothing else in this codebase uses one); the
    router loads `prior_filters`/`prior_messages` from the `copilot_conversations` row
    before invoking and re-saves the updated conversation after."""

    recruiter_id: str
    conversation_id: str
    raw_query: str
    prior_filters: Optional[dict]

    # Router-fetched, read-only inputs (nodes never touch the DB — same convention as
    # candidate_intelligence).
    candidate_pool: list[dict]  # [{candidate_id, skills:[{name,verified}], location,
    #                              experience_years, overall_talent_score, sub_scores:{...},
    #                              github_username, headline, hackathon_experience, repo_summaries:[str]}]
    skill_synonyms: dict[str, list[str]]
    location_aliases: dict[str, list[str]]

    # query_understanding output
    structured_filters: dict

    # hybrid_search output
    shortlist: list[dict]  # candidate dicts, cheap-retrieval-ranked, bounded to ~50

    # reranking output
    ranked_candidate_ids: list[str]

    # explanation output
    explanations: dict[str, str]  # candidate_id -> one-line grounded explanation


class MatchingState(TypedDict):
    """Flow B — per-job batch matching (doc 02 §3)."""

    job_id: str
    job_description: str
    job_required_skills: list[str]
    job_min_experience_years: Optional[int]
    job_location: Optional[str]
    job_is_remote: bool

    # Router-fetched, read-only input.
    candidate_pool: list[dict]  # same shape as CopilotState.candidate_pool (includes sub_scores)

    # job_embed output
    job_embedding: Optional[list[float]]

    # match_candidates output — core (non-project) terms per candidate.
    core_match_scores: dict[str, dict]  # candidate_id -> {skill_similarity, semantic_similarity, experience_match, talent_score_alignment}

    # project_relevance output — separate key from core_match_scores (fan-out from the
    # same predecessor, no reducer needed since the keys don't collide, same pattern as
    # candidate_intelligence's CareerGuidanceState fan-out).
    project_relevance_scores: dict[str, Optional[float]]  # candidate_id -> 0-100 or None

    # score_aggregation output
    match_results: list[dict]  # [{candidate_id, match_percentage, skill_similarity, ...}]
