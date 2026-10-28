"""Recruiter Notification Agent — doc 05 §4/§6. This module's integration boundary is
explicit and narrow (per the member-1 assignment file's §6: "publish the event, stop
here"): build the `hackathon.rankings.finalized` event payload naming the top 3 teams and
their member candidate_ids. Matching those candidates against `recruiter_watchlists` and
surfacing a notification is Module 02's job in a future Phase 2 pass — this node does not
do that matching, only names who the finalized top performers are.

Rule-based (top-N by rank) — no Haiku call. The doc's "templated Haiku message" is
optional UI narrative for the eventual consumer (Module 02's notification copy), not
something this module's own scope needs to produce; kept out per the assignment's
"stop here" instruction rather than building unused narrative generation.
"""

from services.agents.hackathon.state import HackathonRankingState

_TOP_N = 3


async def run(state: HackathonRankingState) -> dict:
    rankings = state.get("final_rankings") or []
    members_by_team = {t["team_id"]: t.get("member_candidate_ids") or [] for t in state["teams"]}

    top_teams = [r["team_id"] for r in rankings if r["composite_score"] is not None][:_TOP_N]
    candidate_ids: list[str] = []
    for team_id in top_teams:
        candidate_ids.extend(members_by_team.get(team_id, []))

    payload = {
        "hackathon_id": state["hackathon_id"],
        "top_teams": top_teams,
        "candidate_ids": candidate_ids,
    }
    return {"notification_event_payload": payload}
