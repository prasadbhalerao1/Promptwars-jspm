"""Flow C — team contribution analytics, batch job over a shared repo (doc 03 §4):

    commit_attribution --> contribution_weighting --> contribution_report --> END
"""

from langgraph.graph import END, START, StateGraph

from services.agents.assessment.nodes import commit_attribution, contribution_report, contribution_weighting
from services.agents.assessment.state import ContributionState


def build_contribution_graph():
    graph = StateGraph(ContributionState)

    graph.add_node("commit_attribution", commit_attribution.run)
    graph.add_node("contribution_weighting", contribution_weighting.run)
    graph.add_node("contribution_report", contribution_report.run)

    graph.add_edge(START, "commit_attribution")
    graph.add_edge("commit_attribution", "contribution_weighting")
    graph.add_edge("contribution_weighting", "contribution_report")
    graph.add_edge("contribution_report", END)

    return graph.compile()


_compiled_contribution_graph = None


def get_contribution_graph():
    global _compiled_contribution_graph
    if _compiled_contribution_graph is None:
        _compiled_contribution_graph = build_contribution_graph()
    return _compiled_contribution_graph
