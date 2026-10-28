"""Salary Prediction node — FR-4.4. Node contract: constraints.md §2.3.

Returns only the keys it changes — runs in parallel with `certification_mapping.run`
and `career_roadmap.run` after `skill_gap_analysis` (see career_guidance_graph.py).

Degrades to a null range (never a fabricated number) both when the Talent Score isn't
computed yet (cold start — same philosophy as the Talent Scoring sub-scores) and when
the trained regression artifact isn't on disk (`SalaryModelUnavailable`) — the latter
doesn't block the rest of career guidance (skill gaps/courses/roadmap are still useful
without it), unlike `CareerGuidanceUnavailable`/`RoadmapGenerationUnavailable` which the
API route surfaces as a hard 503 since they gut FR-4.1/4.3's entire output.
"""

from services.agents.candidate_intelligence.state import CareerGuidanceState
from services.agents.candidate_intelligence.tools.salary_model import (
    SalaryModelUnavailable,
    predict_salary_range,
)


async def run(state: CareerGuidanceState) -> dict:
    talent_score = state.get("talent_score")
    resolved_role = state.get("resolved_target_role") or state.get("target_role") or "Software Engineer"

    if talent_score is None:
        return {
            "salary_estimate_low": None,
            "salary_estimate_high": None,
            "salary_rationale": "Talent Score not yet computed — connect GitHub and/or upload a resume first.",
        }

    try:
        result = predict_salary_range(
            role=resolved_role,
            location=state.get("location"),
            years_experience_proxy=state.get("years_experience_proxy") or 0.0,
            talent_score=talent_score,
        )
    except SalaryModelUnavailable as exc:
        return {
            "salary_estimate_low": None,
            "salary_estimate_high": None,
            "salary_rationale": str(exc),
        }

    return {
        "salary_estimate_low": result.low,
        "salary_estimate_high": result.high,
        "salary_rationale": result.rationale,
    }
