"""Flow B — per-job batch matching (doc 02 §3):

    job_embed --> match_candidates --+--> project_relevance --\
                                      +----------------------->--> score_aggregation --> END

`match_candidates` fans out to both `project_relevance` and `score_aggregation` directly
(the doc's mermaid shows MATCH -> PROJ and MATCH -> AGG as separate edges); LangGraph
runs `score_aggregation` only once both of its predecessors (`match_candidates` AND
`project_relevance`) have completed, since it has two incoming edges. No `Annotated`
reducer is needed — `match_candidates` and `project_relevance` write to different state
keys (`core_match_scores` vs `project_relevance_scores`), so there's no concurrent-write
collision on the same channel.

Invoked synchronously on job creation and on-demand recompute — same "no async job queue
yet" simplification Module 01 uses everywhere else in this codebase.
"""

from langgraph.graph import END, START, StateGraph

from services.agents.recruitment.nodes import job_embed, match_candidates, project_relevance, score_aggregation
from services.agents.recruitment.state import MatchingState


def build_matching_graph():
    graph = StateGraph(MatchingState)

    graph.add_node("job_embed", job_embed.run)
    graph.add_node("match_candidates", match_candidates.run)
    graph.add_node("project_relevance", project_relevance.run)
    graph.add_node("score_aggregation", score_aggregation.run)

    graph.add_edge(START, "job_embed")
    graph.add_edge("job_embed", "match_candidates")
    graph.add_edge("match_candidates", "project_relevance")
    graph.add_edge("match_candidates", "score_aggregation")
    graph.add_edge("project_relevance", "score_aggregation")
    graph.add_edge("score_aggregation", END)

    return graph.compile()


_compiled_matching_graph = None


def get_matching_graph():
    global _compiled_matching_graph
    if _compiled_matching_graph is None:
        _compiled_matching_graph = build_matching_graph()
    return _compiled_matching_graph
