"""Flow A — ingestion & scoring subgraph (doc 01 §3 / doc's mermaid flowchart).

    resume_parser --\
    github_analysis --+--> profile_merge --> talent_scoring --> badge_assignment
    certificate_ocr -/

Runs on signup, GitHub update, or weekly refresh (the last one is a Phase-1 follow-up —
this graph is invoked synchronously from the ingestion routes for now).
"""

from langgraph.graph import END, START, StateGraph

from services.agents.candidate_intelligence.nodes import (
    badge_assignment,
    certificate_ocr,
    github_analysis,
    profile_merge,
    resume_parser,
    talent_scoring,
)
from services.agents.candidate_intelligence.state import CandidateProfileState


def build_graph():
    graph = StateGraph(CandidateProfileState)

    graph.add_node("resume_parser", resume_parser.run)
    graph.add_node("github_analysis", github_analysis.run)
    graph.add_node("certificate_ocr", certificate_ocr.run)
    graph.add_node("profile_merge", profile_merge.run)
    graph.add_node("talent_scoring", talent_scoring.run)
    graph.add_node("badge_assignment", badge_assignment.run)

    graph.add_edge(START, "resume_parser")
    graph.add_edge(START, "github_analysis")
    graph.add_edge(START, "certificate_ocr")
    graph.add_edge("resume_parser", "profile_merge")
    graph.add_edge("github_analysis", "profile_merge")
    graph.add_edge("certificate_ocr", "profile_merge")
    graph.add_edge("profile_merge", "talent_scoring")
    graph.add_edge("talent_scoring", "badge_assignment")
    graph.add_edge("badge_assignment", END)

    return graph.compile()


_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph
