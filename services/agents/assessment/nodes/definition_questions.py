"""Definition Questions Node — generates interview topics from role/JD/years-exp context.
Part of the recruiter-authored interview definition flow."""

from services.agents.assessment.state import DefinitionQuestionState
from services.agents.assessment.tools.interview_llm import generate_definition_questions


async def run(state: DefinitionQuestionState) -> dict:
    topics = await generate_definition_questions(
        state["role_title"],
        state["job_description"],
        state["years_experience"],
        state["question_count"],
    )
    return {"topics": topics}
