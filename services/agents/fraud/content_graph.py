"""AI-Generated Content Signal subgraph — doc 06 §4:

    perplexity_heuristic --> confidence-banded signal --> END

Single node (`nodes/perplexity_heuristic.py` produces both the signal AND the verdict in
one step — there's nothing to combine, unlike the other three subgraphs which merge
multiple independent signals into one verdict). Invoked from
`POST /verification/profiles/{id}/duplicate-check` alongside `duplicate_graph` (no
dedicated route exists for this in doc 06 §6's endpoint list — FR-3 checks resume/written
content, which lives on the same `candidate_profiles`/`generated_documents` subject the
duplicate-check endpoint already reads; see `.agents/decisions.md`'s Module 06 entry).
"""

from langgraph.graph import END, START, StateGraph

from services.agents.fraud.nodes import perplexity_heuristic
from services.agents.fraud.state import FraudCheckState


def build_content_graph():
    graph = StateGraph(FraudCheckState)

    graph.add_node("perplexity_heuristic", perplexity_heuristic.run)

    graph.add_edge(START, "perplexity_heuristic")
    graph.add_edge("perplexity_heuristic", END)

    return graph.compile()


_compiled_content_graph = None


def get_content_graph():
    global _compiled_content_graph
    if _compiled_content_graph is None:
        _compiled_content_graph = build_content_graph()
    return _compiled_content_graph
