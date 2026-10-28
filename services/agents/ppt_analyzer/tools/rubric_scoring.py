"""Problem & Solution Clarity / Innovation & Business Impact / Technical Feasibility
agents — doc 04 §4, all Sonnet, structured rubric scoring at temperature 0 (doc 08 §7).

Real Anthropic calls, same pattern as candidate_intelligence/tools/resume.py: raises
`PitchScoringUnavailable` when `ANTHROPIC_API_KEY` isn't configured or the call fails —
callers (the node functions) catch this and degrade to a `None`-valued RubricScore,
never a fabricated number.
"""

from services.agents.prompts_loader import load_prompt
from services.api.core.config import get_settings
from services.api.core.llm import LLMUnavailable, generate_structured

# Raised when a rubric-scoring LLM call can't run (e.g. no/misconfigured provider key).
PitchScoringUnavailable = LLMUnavailable

# Blank line between the deck text, diagram understanding and repo evidence blocks.
SECTION_SEPARATOR = '\n\n'


async def _call(schema_name: str, schema_description: str, parameters: dict, prompt: str, max_tokens: int | None = None) -> dict:
    settings = get_settings()
    return await generate_structured(
        schema_name=schema_name,
        schema_description=schema_description,
        parameters=parameters,
        prompt=prompt,
        max_tokens=max_tokens or settings.llm_max_tokens_default,
        temperature=settings.llm_temperature_deterministic,
        agent_name=f"ppt_analyzer.rubric.{schema_name}",
    )


_PROBLEM_SOLUTION_PARAMETERS = {
    "type": "object",
    "properties": {
        "score": {"type": "number", "description": "0-100 presentation/clarity quality score"},
        "rationale": {"type": "string"},
        "gaps": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Specific, concrete rubric gaps found (e.g. 'no quantified problem impact stated')",
        },
    },
    "required": ["score", "rationale", "gaps"],
}


async def score_problem_solution(slides_text: str) -> dict:
    prompt = load_prompt("ppt_analyzer", "problem_solution", slides_text=slides_text)
    return await _call(
        "problem_solution_clarity",
        "Rubric-score how clearly a pitch deck states the problem and its proposed solution.",
        _PROBLEM_SOLUTION_PARAMETERS,
        prompt,
    )


_INNOVATION_BUSINESS_PARAMETERS = {
    "type": "object",
    "properties": {
        "innovation_score": {"type": "number", "description": "0-100"},
        "innovation_rationale": {"type": "string"},
        "business_potential_score": {"type": "number", "description": "0-100"},
        "business_potential_rationale": {"type": "string"},
        "gaps": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "innovation_score",
        "innovation_rationale",
        "business_potential_score",
        "business_potential_rationale",
        "gaps",
    ],
}


async def score_innovation_business(slides_text: str, novelty_context: str | None = None) -> dict:
    """Rubric-score innovation and business potential.

    `novelty_context` is currently never supplied. Its only caller used to pass a summary
    of `plagiarism_matches`, which is produced by a graph branch that does not complete
    before the scoring node runs — see the comment in nodes/innovation_business_impact.py.
    The parameter is kept because the prompt has a slot for it and a reordered graph could
    supply it legitimately; it is not dead by oversight.
    """
    context = f"\n\nNovelty signal vs prior submissions: {novelty_context}" if novelty_context else ""
    prompt = load_prompt(
        "ppt_analyzer", "innovation_business", slides_text=slides_text, novelty_context=context
    )
    return await _call(
        "innovation_business_impact",
        "Rubric-score a pitch deck's innovation and business potential.",
        _INNOVATION_BUSINESS_PARAMETERS,
        prompt,
    )


_TECHNICAL_FEASIBILITY_PARAMETERS = {
    "type": "object",
    "properties": {
        "score": {"type": "number", "description": "0-100"},
        "rationale": {"type": "string"},
        "gaps": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["score", "rationale", "gaps"],
}


async def score_technical_feasibility(slides_text: str, ocr_context: str | None, repo_evidence: str | None) -> dict:
    parts = [f"Deck content (per slide):\n{slides_text}"]
    if ocr_context:
        parts.append(f"Diagram/architecture image understanding:\n{ocr_context}")
    if repo_evidence:
        parts.append(f"Evidence from the team's linked repository:\n{repo_evidence}")
    else:
        parts.append(
            "No linked repository evidence is available — score technical feasibility from the deck's "
            "own claims alone and note in gaps that claims are unverified against real code."
        )
    prompt = load_prompt(
        "ppt_analyzer",
        "technical_feasibility",
        context_blocks=SECTION_SEPARATOR.join(parts),
    )
    return await _call(
        "technical_feasibility",
        "Rubric-score a pitch deck's technical depth and feasibility.",
        _TECHNICAL_FEASIBILITY_PARAMETERS,
        prompt,
    )


_SUMMARY_PARAMETERS = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "string",
            "description": "2-3 sentences PER SECTION (problem, solution, market, tech, team if present) — not a slide-by-slide copy",
        },
    },
    "required": ["summary"],
}


async def generate_summary(slides_text: str) -> str:
    prompt = load_prompt("ppt_analyzer", "deck_summary", slides_text=slides_text)
    return (await _call(
        "pitch_summary",
        "Write a grounded per-section summary of a pitch deck.",
        _SUMMARY_PARAMETERS,
        prompt,
    ))["summary"]
