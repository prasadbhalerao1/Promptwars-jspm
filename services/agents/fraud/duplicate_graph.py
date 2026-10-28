"""Duplicate Profile Detection subgraph — doc 06 §4:

    text_fingerprint --> photo_hash --> duplicate_verdict --> END

Doc 06's own mermaid diagram fans `text_fingerprint`/`photo_hash` out from the same
"New/Updated Profile" node in parallel. Sequential here instead: fanning both out from
START in the same LangGraph superstep means both nodes would return a `context` update in
the same step, and `context` isn't an `operator.add`-reduced channel (only `signals` is,
per `state.py`'s docstring) — LangGraph's default "last write wins"/`InvalidUpdateError`
behavior on a plain-overwrite channel is exactly the parallel-fan-out collision documented
in `.agents/decisions.md`'s Module 01 entry. Sequential execution sidesteps it entirely
without needing a dict-merge reducer for a channel most other graphs write to only once.
Runtime cost is negligible (`imagehash`/`datasketch` are both fast local computations, no
network calls), so there's no real latency reason to force the parallel branch here.

Invoked from `POST /verification/profiles/{id}/duplicate-check`. Router pre-fetches the
candidate's own profile text + photo hash, plus a corpus of other candidates' profile
text/photo hashes (Module 01's `candidate_profiles`/`files` tables, read-only) into
`state["context"]`.
"""

from langgraph.graph import END, START, StateGraph

from services.agents.fraud.nodes import duplicate_verdict, photo_hash, text_fingerprint
from services.agents.fraud.state import FraudCheckState


def build_duplicate_graph():
    graph = StateGraph(FraudCheckState)

    graph.add_node("text_fingerprint", text_fingerprint.run)
    graph.add_node("photo_hash", photo_hash.run)
    graph.add_node("duplicate_verdict", duplicate_verdict.run)

    graph.add_edge(START, "text_fingerprint")
    graph.add_edge("text_fingerprint", "photo_hash")
    graph.add_edge("photo_hash", "duplicate_verdict")
    graph.add_edge("duplicate_verdict", END)

    return graph.compile()


_compiled_duplicate_graph = None


def get_duplicate_graph():
    global _compiled_duplicate_graph
    if _compiled_duplicate_graph is None:
        _compiled_duplicate_graph = build_duplicate_graph()
    return _compiled_duplicate_graph
