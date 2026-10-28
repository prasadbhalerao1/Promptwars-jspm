r"""Flow B — AI interview, one `ainvoke()` per turn (doc 03 §4):

    START --(mode=start)--> question --> END
    START --(mode=turn)---> turn_evaluation --(weak, budget left)--> followup --> END
                                          \--(sufficient / topics done)--> question --> END
                                                                        \--(all topics done)--> END

`question` handles both the very-first call (`current_topic_idx == 0`) and being
re-entered after `turn_evaluation` advances the topic index — it always just asks about
whatever `topic_plan[current_topic_idx]` currently is. No LangGraph checkpointer —
`interview_sessions.state` is loaded into initial state and re-saved after each call by
the router, same manual-persistence convention as every other module this session.
"""

from langgraph.graph import END, START, StateGraph

from services.agents.assessment.nodes import followup, question, turn_evaluation
from services.agents.assessment.state import InterviewState


def _route_from_start(state: InterviewState) -> str:
    return "turn_evaluation" if state["mode"] == "turn" else "question"


def _route_after_evaluation(state: InterviewState) -> str:
    if state["last_answer_verdict"] == "weak":
        return "followup"
    if state["interview_status"] == "completed":
        return "__end__"
    return "question"


def build_interview_graph():
    graph = StateGraph(InterviewState)

    graph.add_node("question", question.run)
    graph.add_node("turn_evaluation", turn_evaluation.run)
    graph.add_node("followup", followup.run)

    graph.add_conditional_edges(START, _route_from_start, {"question": "question", "turn_evaluation": "turn_evaluation"})
    graph.add_conditional_edges(
        "turn_evaluation", _route_after_evaluation, {"followup": "followup", "question": "question", "__end__": END}
    )
    graph.add_edge("question", END)
    graph.add_edge("followup", END)

    return graph.compile()


_compiled_interview_graph = None


def get_interview_graph():
    global _compiled_interview_graph
    if _compiled_interview_graph is None:
        _compiled_interview_graph = build_interview_graph()
    return _compiled_interview_graph
