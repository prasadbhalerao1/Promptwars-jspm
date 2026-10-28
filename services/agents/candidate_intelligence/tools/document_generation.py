"""Resume & Cover-Letter Generator Agent — FR-5.1/5.3/5.4, doc 01 §4 ("Resume Generator
Agent | Sonnet | templating + rewriting").

Both generators call Anthropic for real — if `ANTHROPIC_API_KEY` isn't configured,
callers get a clear `DocumentGenerationUnavailable`, matching the
`ResumeExtractionUnavailable` / `StorageUnavailable` pattern used elsewhere in this
module (never silently fabricate a resume/cover letter).

Grounding (FR-5.4's "no fabrication" requirement) is enforced two ways: (1) the prompt
below instructs the model to use ONLY facts present in `merged_profile` and never invent
employers/titles/dates/metrics/skills, and (2) the mandatory Fact-Check Agent
(`tools/fact_check.py`) that runs after every generation — prompt-only enforcement is
not treated as sufficient on its own.
"""

import json

from services.agents.prompts_loader import load_prompt
from services.api.core.llm import LLMUnavailable, generate_structured

_GROUNDING_RULE = (
    "You must use ONLY facts present in the CANDIDATE PROFILE JSON below. Never invent "
    "employers, job titles, dates, metrics, degrees, or skills that are not present in "
    "it. You may rephrase, reorder, and emphasize existing facts, but you may not add "
    "new ones. If the profile lacks enough information for a section, leave it sparse "
    "rather than filling it in."
)

RESUME_GENERATION_PARAMETERS = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "summary": {"type": "string", "description": "2-3 sentence professional summary."},
        "skills": {"type": "array", "items": {"type": "string"}},
        "experience": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "company": {"type": "string"},
                    "years": {"type": "string"},
                    "bullets": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Achievement bullet points, grounded in the profile only.",
                    },
                },
                "required": ["title", "bullets"],
            },
        },
        "education": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "institution": {"type": "string"},
                    "degree": {"type": "string"},
                    "year": {"type": "string"},
                },
            },
        },
    },
    "required": ["headline", "summary", "skills", "experience", "education"],
}

COVER_LETTER_GENERATION_PARAMETERS = {
    "type": "object",
    "properties": {
        "subject": {"type": "string"},
        "body": {
            "type": "string",
            "description": "Full cover letter body text, 3-4 paragraphs.",
        },
    },
    "required": ["subject", "body"],
}


# Raised when the LLM generation call can't run (e.g. no/misconfigured provider key, API failure).
DocumentGenerationUnavailable = LLMUnavailable


async def _call_structured(schema_name: str, schema_description: str, parameters: dict, prompt: str, *, is_fast: bool) -> dict:
    return await generate_structured(
        schema_name=schema_name,
        schema_description=schema_description,
        parameters=parameters,
        prompt=prompt,
        is_fast=is_fast,
        max_tokens=2048,
        agent_name=f"candidate_intelligence.document_generation.{schema_name}",
    )


async def generate_resume_content(merged_profile: dict, target_job_description: str | None) -> dict:
    jd_instruction = (
        (
            "\n\nTARGET JOB DESCRIPTION (FR-5.4 optimization): re-rank and re-word the "
            "experience bullet points to emphasize the skills/keywords below that the "
            "candidate's ACTUAL profile already supports. Do not claim skills the "
            "profile doesn't show just because the JD asks for them.\n\n"
            f"{target_job_description}"
        )
        if target_job_description
        else ""
    )
    prompt = load_prompt(
        "candidate_intelligence",
        "resume_content",
        merged_profile=json.dumps(merged_profile, default=str),
        jd_instruction=jd_instruction,
    )
    return await _call_structured(
        "generated_resume",
        "ATS-friendly resume content generated strictly from the candidate's own profile data.",
        RESUME_GENERATION_PARAMETERS,
        prompt,
        is_fast=False,
    )


async def generate_cover_letter_content(merged_profile: dict, target_job_description: str) -> dict:
    prompt = load_prompt(
        "candidate_intelligence",
        "cover_letter",
        merged_profile=json.dumps(merged_profile, default=str),
        target_job_description=target_job_description,
    )
    return await _call_structured(
        "generated_cover_letter",
        "A cover letter grounded strictly in the candidate's own profile data.",
        COVER_LETTER_GENERATION_PARAMETERS,
        prompt,
        is_fast=False,
    )
