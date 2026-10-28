"""Verification Report Agent — FR-1, doc 03 §4's join of the Grading + LLM Code Review
branches. Rules only. Node contract: constraints.md §2.3.

Scoring: for `coding`/`mcq`, correctness (tests passed) dominates — the LLM review only
nudges the score for `coding` (readability/architecture matter, but a wrong answer is a
wrong answer). For `project_analysis` there are no tests at all, so the score comes
entirely from the LLM review, discounted by any red flags found.
"""

from services.agents.assessment.state import VerificationState

# How much the LLM review can move a `coding` score off the test-pass-rate baseline —
# deliberately small so review quality never overrides objective correctness.
_CODING_REVIEW_WEIGHT = 0.15
_RED_FLAG_PENALTY = 8.0  # points off per red flag, project_analysis only


async def run(state: VerificationState) -> dict:
    assessment_type = state["assessment_type"]
    review = state.get("llm_review")

    if assessment_type in ("coding", "mcq"):
        tests_total = state.get("tests_total") or 0
        tests_passed = state.get("tests_passed") or 0
        base = (100.0 * tests_passed / tests_total) if tests_total else 0.0

        if assessment_type == "coding" and review:
            review_avg = ((review.get("readability") or 0) + (review.get("architecture") or 0)) / 2
            score = (1 - _CODING_REVIEW_WEIGHT) * base + _CODING_REVIEW_WEIGHT * review_avg
        else:
            score = base
        return {"score": round(max(0.0, min(100.0, score)), 1)}

    # project_analysis
    if not review:
        return {"score": None}
    review_avg = ((review.get("readability") or 0) + (review.get("architecture") or 0)) / 2
    penalty = _RED_FLAG_PENALTY * len(review.get("red_flags") or [])
    return {"score": round(max(0.0, min(100.0, review_avg - penalty)), 1)}
