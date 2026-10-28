"""Separate on-demand subgraph for the Interview Report Agent — see
`nodes/interview_report.py`'s docstring for why this isn't folded into
`interview_graph.py`."""

from langgraph.graph import END, START, StateGraph

from services.agents.assessment.nodes import interview_report
from services.agents.assessment.state import InterviewReportState


def build_interview_report_graph():
    graph = StateGraph(InterviewReportState)
    graph.add_node("interview_report", interview_report.run)
    graph.add_edge(START, "interview_report")
    graph.add_edge("interview_report", END)
    return graph.compile()


_compiled_interview_report_graph = None


def get_interview_report_graph():
    global _compiled_interview_report_graph
    if _compiled_interview_report_graph is None:
        _compiled_interview_report_graph = build_interview_report_graph()
    return _compiled_interview_report_graph
