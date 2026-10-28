"""Career Roadmap node — FR-4.3. Node contract: constraints.md §2.3.

Returns only the keys it changes — runs in parallel with `certification_mapping.run`
and `salary_prediction.run` after `skill_gap_analysis` (see career_guidance_graph.py).
"""

from services.agents.candidate_intelligence.state import CareerGuidanceState
from services.agents.candidate_intelligence.tools.roadmap import generate_roadmap


async def run(state: CareerGuidanceState) -> dict:
    gaps = state.get("skill_gaps") or []
    if not gaps:
        return {"roadmap": {"stages": []}}

    roadmap = await generate_roadmap(
        target_role=state.get("resolved_target_role") or state.get("target_role") or "the target role",
        skill_gaps=[g["skill"] for g in gaps],
        covered_skills=state.get("covered_skills") or [],
    )
    return {"roadmap": roadmap}
