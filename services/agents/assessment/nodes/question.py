"""Question Agent — FR-2.1. Node contract: constraints.md §2.3. Asks about
`topic_plan[current_topic_idx]` — used both for the very first question (session start,
`current_topic_idx == 0`) and for advancing to a new topic after `turn_evaluation`
decided the previous topic is done."""

from services.agents.assessment.state import InterviewState
from services.agents.assessment.tools.interview_llm import generate_question


async def run(state: InterviewState) -> dict:
    topic_plan = state["topic_plan"]
    idx = state["current_topic_idx"]

    if idx >= len(topic_plan):
        return {"next_question": None, "interview_status": "completed"}

    question = await generate_question(
        topic_plan[idx],
        state["candidate_profile_summary"],
        state["transcript"],
        state.get("job_context"),
    )
    return {
        "next_question": question,
        "interview_status": "in_progress",
        "transcript": [*state["transcript"], {"role": "agent", "text": question}],
    }
