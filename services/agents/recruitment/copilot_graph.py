"""Flow A — Recruiter Copilot (doc 02 §3):

    query_understanding -> search_plan -> hybrid_search -> reranking -> explanation -> END

One `ainvoke()` per conversational turn — the doc's mermaid shows a loop back to
"Understand the Query" on follow-up refinement, but since no LangGraph checkpointer is
used anywhere in this codebase, that loop is realized at the router level instead: each
turn is a fresh graph run, with the previous turn's `structured_filters` passed in as
`prior_filters` so `query_understanding` can merge a refinement rather than starting over.
"""

from langgraph.graph import END, START, StateGraph

from services.agents.recruitment.nodes import (
    explanation,
    hybrid_search,
    query_understanding,
    reranking,
    search_plan,
)
from services.agents.recruitment.state import CopilotState


def build_copilot_graph():
    graph = StateGraph(CopilotState)

    graph.add_node("query_understanding", query_understanding.run)
    graph.add_node("search_plan", search_plan.run)
    graph.add_node("hybrid_search", hybrid_search.run)
    graph.add_node("reranking", reranking.run)
    graph.add_node("explanation", explanation.run)

    graph.add_edge(START, "query_understanding")
    graph.add_edge("query_understanding", "search_plan")
    graph.add_edge("search_plan", "hybrid_search")
    graph.add_edge("hybrid_search", "reranking")
    graph.add_edge("reranking", "explanation")
    graph.add_edge("explanation", END)

    return graph.compile()


_compiled_copilot_graph = None


def get_copilot_graph():
    global _compiled_copilot_graph
    if _compiled_copilot_graph is None:
        _compiled_copilot_graph = build_copilot_graph()
    return _compiled_copilot_graph
