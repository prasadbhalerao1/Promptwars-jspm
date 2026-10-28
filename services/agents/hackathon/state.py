from typing import Optional, TypedDict


class HackathonRankingState(TypedDict):
    """Finalize-rankings pass (doc 05 §4), one `ainvoke()` per hackathon. Ingestion
    (CSV/webhook/direct — the Normalization Agent's job) happens before any of this, at
    submission time, directly in the router — there's no per-submission graph, matching
    every other module's "no LangGraph checkpointer, router does the fetch/persist"
    convention.

    Router pre-fetches `pitch_score`/`plagiarism_similarities` per team (plain reads of
    Module 04's `presentation_scores`/`plagiarism_matches` tables) before invoking this
    graph — those are never recomputed here, only the repo side (which doc 05 must
    actively trigger, since a hackathon repo link never goes through Module 03's own
    submission UI) is computed inside the graph.
    """

    hackathon_id: str
    scoring_config: Optional[dict]  # {judge_score_component: 0.40, pitch_score_component: 0.30, ...} from Hackathon.scoring_config, or None for defaults
    teams: list[dict]
    # Each team dict: {team_id, repo_url, presentation_id, judge_score,
    #                  pitch_score: float|None (pre-fetched), plagiarism_similarities: list[float] (pre-fetched)}

    # repo_deck_linking output
    repo_scores: dict[str, Optional[float]]  # team_id -> doc-03 Submission.score
    repo_verification_results: dict[str, dict]  # team_id -> newly-computed {repo_full_name, static_analysis, llm_review, score}, for the router to persist

    # cross_event_novelty output
    novelty_scores: dict[str, Optional[float]]  # team_id -> 0-100

    # ranking_aggregation output
    final_rankings: list[dict]  # ordered [{team_id, rank, composite_score, score_breakdown}]

    # recruiter_notification output
    notification_event_payload: Optional[dict]  # {hackathon_id, top_teams, candidate_ids}
