"""Career Roadmaps — FR-4.3. LLM-generated staged roadmap (structured output: stages
-> skills -> estimated timeline), doc 01 §5 routes this to Sonnet ("judgment" tier —
same routing as Talent Scoring's Project Quality/Innovation).

Same convention as `tools/resume.py`'s structured extraction: calls Anthropic for real,
raises a clear `RoadmapGenerationUnavailable` when the API key is missing or the call
fails — never a fabricated roadmap.
"""

from services.agents.prompts_loader import load_prompt
from services.api.core.config import get_settings
from services.api.core.llm import LLMUnavailable, generate_structured

ROADMAP_PARAMETERS = {
    "type": "object",
    "properties": {
        "stages": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "stage": {"type": "string", "description": "Short stage name, e.g. 'Foundations'"},
                    "skills": {"type": "array", "items": {"type": "string"}},
                    "estimated_weeks": {"type": "number"},
                    "description": {"type": "string"},
                },
                "required": ["stage", "skills", "estimated_weeks"],
            },
        }
    },
    "required": ["stages"],
}


# Raised when the LLM roadmap call can't run (e.g. no/misconfigured provider key).
RoadmapGenerationUnavailable = LLMUnavailable


async def generate_roadmap(target_role: str, skill_gaps: list[str], covered_skills: list[str]) -> dict:
    if not skill_gaps:
        return {"stages": []}

    prompt = load_prompt(
        "candidate_intelligence",
        "career_roadmap",
        target_role=target_role,
        covered_skills=", ".join(covered_skills) or "no verified skills yet",
        skill_gaps=", ".join(skill_gaps),
    )
    return await generate_structured(
        schema_name="career_roadmap",
        schema_description="A staged learning roadmap to close a candidate's skill gaps for a target role.",
        parameters=ROADMAP_PARAMETERS,
        prompt=prompt,
        max_tokens=get_settings().llm_max_tokens_large,
        agent_name="candidate_intelligence.roadmap",
    )
