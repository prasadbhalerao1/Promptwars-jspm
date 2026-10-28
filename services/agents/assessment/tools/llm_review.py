"""LLM Code Review Agent (FR-1.3, judgment-tier) and the Grading Agent's partial-credit
rationale (fast-tier). Routed through `services.api.core.llm.generate_structured` so
this works against whichever provider `LLM_PROVIDER` selects (Anthropic in production,
Groq for testing — see `.env`) and is traced the same way regardless.
"""

import json

from services.agents.prompts_loader import load_prompt
from services.api.core.config import get_settings
from services.api.core.llm import LLMUnavailable, generate_structured

__all__ = ["AssessmentUnavailable", "review_code", "grading_rationale"]

# Re-exported under this module's historical name — every other tool file in this
# package imports `AssessmentUnavailable` from here.
AssessmentUnavailable = LLMUnavailable

_CODE_REVIEW_PARAMETERS = {
    "type": "object",
    "properties": {
        "readability": {"type": "number", "description": "0-100"},
        "architecture": {"type": "number", "description": "0-100"},
        "red_flags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Concrete issues only (e.g. 'copy-pasted boilerplate unmodified', 'no error handling on the happy path assumed to fail'). Empty array if none.",
        },
        "rationale": {"type": "string"},
    },
    "required": ["readability", "architecture", "red_flags", "rationale"],
}

_GRADING_RATIONALE_PARAMETERS = {
    "type": "object",
    "properties": {"rationale": {"type": "string"}},
    "required": ["rationale"],
}


async def review_code(problem_statement: str, source: str, static_analysis: dict) -> dict:
    """Grounded in the actual submitted source and the deterministic static-analysis
    findings above it — never invents an architectural judgment unrelated to what's
    actually in the code."""
    prompt = load_prompt(
        "assessment",
        "llm_code_review",
        problem_statement=problem_statement,
        source=source,
        static_analysis=json.dumps(static_analysis, default=str),
    )
    return await generate_structured(
        schema_name="code_review",
        schema_description="Structured rubric review of submitted source code.",
        parameters=_CODE_REVIEW_PARAMETERS,
        prompt=prompt,
        agent_name="assessment.llm_code_review",
    )


async def grading_rationale(problem_statement: str, tests_passed: int, tests_total: int, source: str) -> str | None:
    """Only called for near-miss submissions (some but not all tests passing) — a clean
    pass or a total fail needs no LLM rationale, the numbers already say it. Best-effort:
    returns `None` rather than raising if the configured provider is unavailable."""
    prompt = load_prompt(
        "assessment",
        "grading_rationale",
        problem_statement=problem_statement,
        tests_passed=tests_passed,
        tests_total=tests_total,
        source=source,
    )
    try:
        result = await generate_structured(
            schema_name="partial_credit_rationale",
            schema_description="One short sentence explaining a near-miss test result for partial credit.",
            parameters=_GRADING_RATIONALE_PARAMETERS,
            prompt=prompt,
            is_fast=True,
            max_tokens=get_settings().llm_max_tokens_small,
            agent_name="assessment.grading_rationale",
        )
    except LLMUnavailable:
        return None
    return result.get("rationale")
