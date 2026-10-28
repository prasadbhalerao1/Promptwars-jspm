"""Ranking Aggregation Agent — doc 05 §4, "rules (weighted formula, transparent)".
Node contract: constraints.md §2.3. Joins `repo_scores` (from `repo_deck_linking`) with
`novelty_scores` (from `cross_event_novelty`) and each team's pre-fetched `judge_score`/
`pitch_score` into the doc 08 §8 composite formula, then ranks. Teams with no computable
composite (every component N/A — e.g. no judge score, no deck, no repo) sort last and are
still included with `composite_score: None`, never silently dropped.
"""

from services.agents.hackathon.state import HackathonRankingState
from services.agents.hackathon.tools.ranking import compute_composite_score


async def run(state: HackathonRankingState) -> dict:
    repo_scores = state.get("repo_scores") or {}
    novelty_scores = state.get("novelty_scores") or {}
    scoring_config = state.get("scoring_config")  # None -> uses _DEFAULT_WEIGHTS in compute_composite_score

    results = []
    for team in state["teams"]:
        team_id = team["team_id"]
        composite, breakdown = compute_composite_score(
            judge_score=team.get("judge_score"),
            pitch_score=team.get("pitch_score"),
            repo_score=repo_scores.get(team_id),
            novelty_score=novelty_scores.get(team_id),
            weights=scoring_config,
        )
        results.append({"team_id": team_id, "composite_score": composite, "score_breakdown": breakdown})

    results.sort(key=lambda r: (r["composite_score"] is None, -(r["composite_score"] or 0)))
    for idx, r in enumerate(results, start=1):
        r["rank"] = idx

    return {"final_rankings": results}
