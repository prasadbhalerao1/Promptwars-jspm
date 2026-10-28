"""Supervisor intent classifier — Haiku, structured tool-use output. Same pattern as
Module 02's Query Understanding Agent
(`services/agents/recruitment/tools/copilot_llm.py:understand_query`): a tool-use schema,
`tool_choice` forced to that one tool, a typed `*Unavailable` exception raised (never a
silent fallback/guess) when the API key is missing, the call fails, or the model doesn't
return the structured tool output.
"""

from services.api.core.llm import LLMUnavailable, generate_structured

# Raised when the supervisor's intent classifier can't run — missing/misconfigured
# provider key, an API error, or malformed structured output. Never silently guessed;
# the router maps this to a typed 503, matching every other module's
# `RecruitmentUnavailable`/`ResumeExtractionUnavailable`/etc. convention.
SupervisorUnavailable = LLMUnavailable


_INTENT_PARAMETERS = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": ["candidate_score", "job_match"],
            "description": (
                "'candidate_score': the request is asking about ONE candidate's Talent "
                "Score, sub-scores, or overall profile strength. 'job_match': the "
                "request is asking which candidates match a specific job posting, or "
                "to (re)compute/fetch matches for a job."
            ),
        },
        "rationale": {
            "type": "string",
            "description": "One sentence explaining why this intent was chosen.",
        },
    },
    "required": ["intent", "rationale"],
}


async def classify_intent(raw_request: str) -> dict:
    from services.agents.prompts_loader import load_prompt

    prompt = load_prompt("supervisor", "classifier", query=raw_request)
    return await generate_structured(
        schema_name="classified_intent",
        schema_description="Classify which platform module should handle this natural-language request.",
        parameters=_INTENT_PARAMETERS,
        prompt=prompt,
        is_fast=True,
        max_tokens=512,
        agent_name="supervisor.classify_intent",
    )
