"""On-demand subgraph for generating interview definition topics from role context."""

from langgraph.graph import END, START, StateGraph

from services.agents.assessment.nodes import definition_questions
from services.agents.assessment.state import DefinitionQuestionState


def build_interview_definition_graph():
    graph = StateGraph(DefinitionQuestionState)
    graph.add_node("definition_questions", definition_questions.run)
    graph.add_edge(START, "definition_questions")
    graph.add_edge("definition_questions", END)
    return graph.compile()


_compiled_interview_definition_graph = None


def get_interview_definition_graph():
    global _compiled_interview_definition_graph
    if _compiled_interview_definition_graph is None:
        _compiled_interview_definition_graph = build_interview_definition_graph()
    return _compiled_interview_definition_graph
