"""Grading Agent — FR-1.1/1.2, "rules (pass/fail count) + Haiku for partial-credit
rationale on near-misses" per doc 03 §5. Node contract: constraints.md §2.3.

`test_results` for `coding` assessments is already pass/fail-only, computed client-side
in the candidate's browser sandbox (doc 03 §2) — this node counts, it never re-executes
or second-guesses the client's reported result. `mcq` grading compares submitted answers
against `spec`'s answer key directly (rules only, no LLM needed for exact-match grading).
`project_analysis` has no pass/fail concept — grading is a no-op passthrough, scoring
comes entirely from the LLM Code Review Agent + static analysis in `verification_report`.
"""

from services.agents.assessment.state import VerificationState
from services.agents.assessment.tools.llm_review import grading_rationale


async def run(state: VerificationState) -> dict:
    assessment_type = state["assessment_type"]

    if assessment_type == "coding":
        results = state.get("test_results") or []
        tests_total = len(results)
        tests_passed = sum(1 for r in results if r.get("passed"))
        rationale = None
        if 0 < tests_passed < tests_total:
            rationale = await grading_rationale(
                state["spec"].get("problem_statement", ""),
                tests_passed,
                tests_total,
                state["code_or_answers"].get("code", ""),
            )
        return {"tests_passed": tests_passed, "tests_total": tests_total, "grading_rationale": rationale}

    if assessment_type == "mcq":
        answer_key = {q["id"]: q["correct_answer"] for q in state["spec"].get("questions", [])}
        submitted = state["code_or_answers"].get("answers", {})
        tests_total = len(answer_key)
        tests_passed = sum(1 for qid, correct in answer_key.items() if submitted.get(qid) == correct)
        return {"tests_passed": tests_passed, "tests_total": tests_total, "grading_rationale": None}

    return {"tests_passed": 0, "tests_total": 0, "grading_rationale": None}
