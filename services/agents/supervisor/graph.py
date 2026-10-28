"""Supervisor graph — minimal demo per doc/multi-agent-architecture/07 §2, dispatching a
raw NL request to real Module 01 (Candidate Intelligence) and Module 02 (Recruitment)
logic in-process. Proves the supervisor pattern end-to-end for 2 of the 4 modules that
exist so far — see `state.py`'s docstring for why this doesn't cover all 6.

Two things doc 07 §2's example code assumes that this codebase does NOT actually have —
built around them here, not silently "fixed" (both logged in `.agents/decisions.md`):

1. `builder.compile(checkpointer=postgres_checkpointer)` — no module in this codebase uses
   a LangGraph checkpointer. Module 02's Recruiter Copilot and Module 03's Interview
   Agent both persist state to DB columns manually instead (see `.agents/decisions.md`'s
   Module 02/03 entries). Compiled without one here too, as a module-level `get_graph()`
   singleton — same pattern as `services/agents/candidate_intelligence/graph.py`.
2. Each module's real entry point is a REST router step (fetch DB context -> build state
   -> invoke its own subgraph -> persist -> respond), not a bare importable subgraph this
   supervisor can `ainvoke()` and expect DB I/O to already be done. This supervisor's
   per-module nodes instead call the exact service functions the routers themselves call
   (`services.api.modules.candidates.router._to_score_response`,
   `services.api.modules.recruitment.router._run_matching_and_persist`) — doing real DB reads/
   writes, not a mock. The live `AsyncSession` is threaded through via
   `RunnableConfig.configurable["db"]` (LangGraph's supported per-invocation context
   mechanism) rather than through `SupervisorState` itself, since a plain state dict
   isn't the right place to carry a live DB session object across a module-level singleton
   graph shared by concurrent requests.
"""

from langgraph.graph import END, StateGraph

from services.agents.supervisor.nodes import candidate_intelligence, classify_intent, recruitment
from services.agents.supervisor.state import SupervisorState


# The only two branches the conditional edge map below knows about. An intent outside
# this set reaches LangGraph as an unmapped key and raises at dispatch time rather than
# degrading. The classifier's JSON schema constrains the value, but schema enforcement
# varies by provider (this gateway also serves Groq/Gemini/Ollama through the
# OpenAI-compatible path), so the guard is real rather than theoretical.
_ROUTABLE_INTENTS = ("candidate_score", "job_match")


def _route(state: SupervisorState) -> str:
    intent = state.get("intent")
    if intent not in _ROUTABLE_INTENTS:
        # `or "candidate_score"` only covered None and empty string, not an unexpected
        # non-empty value. Fall back to the narrower read-only branch for anything
        # unrecognized, matching the classifier prompt's own tie-break rule.
        return "candidate_score"
    return intent


def build_graph():
    graph = StateGraph(SupervisorState)

    graph.add_node("classify_intent", classify_intent.run)
    graph.add_node("candidate_intelligence", candidate_intelligence.run)
    graph.add_node("recruitment", recruitment.run)

    graph.set_entry_point("classify_intent")
    graph.add_conditional_edges(
        "classify_intent",
        _route,
        {
            "candidate_score": "candidate_intelligence",
            "job_match": "recruitment",
        },
    )
    graph.add_edge("candidate_intelligence", END)
    graph.add_edge("recruitment", END)

    return graph.compile()


_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph
