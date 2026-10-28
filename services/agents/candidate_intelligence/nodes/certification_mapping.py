"""Certification Mapping node — FR-4.2 (Recommended Certifications) & FR-4.5 (Learning
Recommendations share the same catalog, filtered by gap priority — `skill_gaps` is
already gap-priority-sorted by `skill_gap_analysis`, so a single pass covers both FRs).
Node contract: constraints.md §2.3.

Returns only the keys it changes — runs in parallel with `career_roadmap.run` and
`salary_prediction.run` after `skill_gap_analysis` (see career_guidance_graph.py).
"""

from services.agents.candidate_intelligence.state import CareerGuidanceState
from services.agents.candidate_intelligence.tools.course_catalog import match_courses


async def run(state: CareerGuidanceState) -> dict:
    gap_skill_names = [g["skill"] for g in state.get("skill_gaps") or []]
    courses = match_courses(state.get("course_catalog") or [], gap_skill_names)
    return {"recommended_courses": courses}
