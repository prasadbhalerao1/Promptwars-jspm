"""Flow A — skill verification (doc 03 §4):

    static_analysis --+--> grading --------\
                       +--> llm_code_review --+--> verification_report --> END

One `ainvoke()` per submission. `static_analysis` fans out to both `grading` (which only
reads `code_or_answers`/`test_results`, not `static_analysis`, but is sequenced after it
so the near-miss rationale call can eventually reference it if extended) and
`llm_code_review` (which does read `static_analysis`) — no reducer needed, they write
different state keys (`tests_passed`/`tests_total`/`grading_rationale` vs `llm_review`),
same no-collision pattern as every other fan-out this session.
"""

from langgraph.graph import END, START, StateGraph

from services.agents.assessment.nodes import grading, llm_code_review, static_analysis, verification_report
from services.agents.assessment.state import VerificationState


def build_verification_graph():
    graph = StateGraph(VerificationState)

    graph.add_node("static_analysis", static_analysis.run)
    graph.add_node("grading", grading.run)
    graph.add_node("llm_code_review", llm_code_review.run)
    graph.add_node("verification_report", verification_report.run)

    graph.add_edge(START, "static_analysis")
    graph.add_edge("static_analysis", "grading")
    graph.add_edge("static_analysis", "llm_code_review")
    graph.add_edge("grading", "verification_report")
    graph.add_edge("llm_code_review", "verification_report")
    graph.add_edge("verification_report", END)

    return graph.compile()


_compiled_verification_graph = None


def get_verification_graph():
    global _compiled_verification_graph
    if _compiled_verification_graph is None:
        _compiled_verification_graph = build_verification_graph()
    return _compiled_verification_graph
