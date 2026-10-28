"""Problem & Solution Clarity Agent — doc 04 §4 (FR-3). Node contract: constraints.md §2.3.

Its output becomes the "Presentation Quality" component of the Overall Pitch Score
(doc 08 §7) — see packages/shared_schemas/presentations.py's module docstring for why.
"""

from services.agents.ppt_analyzer.state import PitchAnalysisState
from services.agents.ppt_analyzer.tools.rubric_scoring import PitchScoringUnavailable, score_problem_solution
from services.agents.ppt_analyzer.tools.text import slides_text
from services.api.core.llm import validated_score


async def run(state: PitchAnalysisState) -> dict:
    slides = state.get("slides") or []
    if not slides:
        return {"presentation_quality": {"value": None, "rationale": "No slide text extracted.", "gaps": []}}

    try:
        result = await score_problem_solution(slides_text(slides))
        return {
            "presentation_quality": {
                "value": validated_score(result.get("score")),
                "rationale": result.get("rationale"),
                "gaps": result.get("gaps", []),
            }
        }
    except PitchScoringUnavailable as exc:
        return {"presentation_quality": {"value": None, "rationale": f"unavailable: {exc}", "gaps": []}}
