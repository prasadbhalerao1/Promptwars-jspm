"""Aggregation Agent — doc 04 §4, formula in doc 08 §7. Node contract: constraints.md §2.3.

Joins all 5 parallel branches (problem_solution_clarity, innovation_business_impact,
technical_feasibility, similarity_plagiarism, ai_content_heuristic) — LangGraph waits
for all 5 predecessor edges before running this node.
"""

from services.agents.ppt_analyzer.state import PitchAnalysisState
from services.agents.ppt_analyzer.tools.aggregate import compute_overall_pitch_score
from services.agents.ppt_analyzer.tools.problem_rubric_engine import evaluate_deck_with_rubric


async def run(state: PitchAnalysisState) -> dict:
    presentation_quality = state.get("presentation_quality") or {"value": None}
    innovation_business = state.get("innovation_business") or {}
    innovation = innovation_business.get("innovation", {"value": None})
    business_potential = innovation_business.get("business_potential", {"value": None})
    technical_feasibility = state.get("technical_feasibility") or {"value": None}

    legacy_scores = {
        "innovation": innovation,
        "technical_feasibility": technical_feasibility,
        "presentation_quality": presentation_quality,
        "business_potential": business_potential,
    }

    # Run comprehensive problem-statement-aligned rubric evaluation
    rubric_result = await evaluate_deck_with_rubric(
        slides=state.get("slides") or [],
        problem_statement=state.get("problem_statement"),
        linked_repo=state.get("linked_repo"),
    )

    rubric_breakdown = rubric_result.get("rubric_breakdown") or {}
    requirement_coverage = rubric_result.get("requirement_coverage") or []
    rubric_overall = rubric_result.get("overall_pitch_score")

    overall, renormalized = compute_overall_pitch_score({name: s.get("value") for name, s in legacy_scores.items()})

    # Prefer the grounded rubric score if available
    effective_overall = rubric_overall if rubric_overall is not None else overall

    return {
        "scores": legacy_scores,
        "overall_score": effective_overall,
        "renormalized_scores": renormalized,
        "rubric_breakdown": rubric_breakdown,
        "requirement_coverage": requirement_coverage,
    }
