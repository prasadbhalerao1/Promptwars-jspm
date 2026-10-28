"""LLM Code Review Agent — FR-1.3. Node contract: constraints.md §2.3. Runs for `coding`
and `project_analysis` submissions (the router fetches and injects sampled repo source
into `code_or_answers["code"]` for `project_analysis` before invoking the graph, so this
node treats both types identically); skipped for `mcq` (no source to review)."""

from services.agents.assessment.state import VerificationState
from services.agents.assessment.tools.llm_review import review_code


async def run(state: VerificationState) -> dict:
    if state["assessment_type"] == "mcq":
        return {"llm_review": None}

    source = state["code_or_answers"].get("code", "")
    if not source:
        return {"llm_review": None}

    review = await review_code(
        state["spec"].get("problem_statement", ""), source, state.get("static_analysis") or {}
    )
    return {"llm_review": review}
