"""Follow-up Agent — FR-2.1. Node contract: constraints.md §2.3. Only reached when
`turn_evaluation` judged the last answer weak and the topic still has follow-up budget."""

from services.agents.assessment.state import InterviewState
from services.agents.assessment.tools.interview_llm import generate_followup


async def run(state: InterviewState) -> dict:
    transcript = state["transcript"]
    answer_turn = transcript[-1]
    question_turn = transcript[-2] if len(transcript) >= 2 else {"text": ""}
    topic = state["topic_plan"][state["current_topic_idx"]]

    question = await generate_followup(topic, question_turn["text"], answer_turn["text"])
    return {
        "next_question": question,
        "interview_status": "in_progress",
        "transcript": [*transcript, {"role": "agent", "text": question}],
    }
