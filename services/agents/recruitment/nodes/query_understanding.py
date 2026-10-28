"""Query Understanding Agent — FR-3.1/3.2. Node contract: constraints.md §2.3."""

from services.agents.recruitment.state import CopilotState
from services.agents.recruitment.tools.copilot_llm import understand_query
from services.agents.recruitment.tools.taxonomy import resolve_location, resolve_skill


async def run(state: CopilotState) -> dict:
    raw = await understand_query(state["raw_query"], state.get("prior_filters"))

    skill_synonyms = state.get("skill_synonyms") or {}
    location_aliases = state.get("location_aliases") or {}

    structured_filters = {
        "location": resolve_location(raw["location"], location_aliases) if raw.get("location") else None,
        "skills": [resolve_skill(s, skill_synonyms) for s in raw.get("skills", [])],
        "min_talent_score": raw.get("min_talent_score"),
        "hackathon_experience": raw.get("hackathon_experience"),
        "remote_ok": raw.get("remote_ok"),
        "semantic_query": raw.get("semantic_query", ""),
    }
    return {"structured_filters": structured_filters}
