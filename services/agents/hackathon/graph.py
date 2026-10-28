"""Finalize-rankings graph (doc 05 §3/§4):

    repo_deck_linking --> cross_event_novelty --> ranking_aggregation --> recruiter_notification --> END

Sequential, not fanned-out: `ranking_aggregation` needs both `repo_scores` (from
`repo_deck_linking`) and `novelty_scores` (from `cross_event_novelty`) fully resolved
before it can compute a composite, and `recruiter_notification` needs the finished
`final_rankings` to know who the top teams are — there's no independent branch to
parallelize here, unlike Module 01/02's fan-out graphs.

Invoked synchronously from `POST /hackathons/{id}/rankings/finalize` — same "no async job
queue yet" simplification every other module in this codebase uses, and doc 05 §10's own
"idempotent and re-runnable" NFR (organizers can finalize again after correcting a judge
score; the router upserts `hackathon_rankings` keyed on `(hackathon_id, team_id)` rather
than inserting a second set of rows).
"""

from langgraph.graph import END, START, StateGraph

from services.agents.hackathon.nodes import (
    cross_event_novelty,
    ranking_aggregation,
    recruiter_notification,
    repo_deck_linking,
)
from services.agents.hackathon.state import HackathonRankingState


def build_hackathon_ranking_graph():
    graph = StateGraph(HackathonRankingState)

    graph.add_node("repo_deck_linking", repo_deck_linking.run)
    graph.add_node("cross_event_novelty", cross_event_novelty.run)
    graph.add_node("ranking_aggregation", ranking_aggregation.run)
    graph.add_node("recruiter_notification", recruiter_notification.run)

    graph.add_edge(START, "repo_deck_linking")
    graph.add_edge("repo_deck_linking", "cross_event_novelty")
    graph.add_edge("cross_event_novelty", "ranking_aggregation")
    graph.add_edge("ranking_aggregation", "recruiter_notification")
    graph.add_edge("recruiter_notification", END)

    return graph.compile()


_compiled_hackathon_ranking_graph = None


def get_hackathon_ranking_graph():
    global _compiled_hackathon_ranking_graph
    if _compiled_hackathon_ranking_graph is None:
        _compiled_hackathon_ranking_graph = build_hackathon_ranking_graph()
    return _compiled_hackathon_ranking_graph
