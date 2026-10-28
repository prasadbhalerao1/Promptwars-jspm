"""Flow B — on-demand resume/cover-letter builder subgraph (doc 01 §3's mermaid):

    Candidate Requests Document -> Generate -> Fact-Check
        Fact-Check "looks accurate"        -> Deliver
        Fact-Check "found unsupported claim" -> back to Generate

Separate from `graph.py`'s Flow A (ingestion & scoring) — this one runs per-request from
the API (resume/cover-letter generate endpoints), not on signup/GitHub-webhook/cron.

Capped at `MAX_ATTEMPTS` regenerate-and-recheck cycles so an LLM that keeps producing
unsupported claims can't loop forever; if still failing after the cap, the graph ends
with `fact_check_status == "failed"` and the API layer refuses to hand the document to
the candidate (see `services/api/routers/candidates.py`) rather than deliver an
unverified one.
"""

from langgraph.graph import END, START, StateGraph

from services.agents.candidate_intelligence.document_state import DocumentBuilderState
from services.agents.candidate_intelligence.nodes import document_generator, fact_check
from services.api.core.config import get_settings

MAX_ATTEMPTS = get_settings().document_generation_max_attempts


def _route_after_generation(state: DocumentBuilderState) -> str:
    if state.get("generation_error"):
        return END
    return "fact_check"


def _route_after_fact_check(state: DocumentBuilderState) -> str:
    if state.get("fact_check_status") == "passed":
        return END
    if state.get("attempts", 0) >= MAX_ATTEMPTS:
        return END
    return "document_generator"


def build_resume_graph():
    graph = StateGraph(DocumentBuilderState)

    graph.add_node("document_generator", document_generator.run)
    graph.add_node("fact_check", fact_check.run)

    graph.add_edge(START, "document_generator")
    graph.add_conditional_edges(
        "document_generator", _route_after_generation, ["fact_check", END]
    )
    graph.add_conditional_edges(
        "fact_check", _route_after_fact_check, ["document_generator", END]
    )

    return graph.compile()


_compiled_resume_graph = None


def get_resume_graph():
    global _compiled_resume_graph
    if _compiled_resume_graph is None:
        _compiled_resume_graph = build_resume_graph()
    return _compiled_resume_graph
