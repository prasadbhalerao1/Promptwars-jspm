"""Skill Gap Analysis node — FR-4.1. Node contract: constraints.md §2.3.

Runs first in the career-guidance graph (see `career_guidance_graph.py`) since
`certification_mapping`, `career_roadmap`, and `salary_prediction` all consume its
`resolved_target_role`/`skill_gaps` output. Returns only the keys it changes (see
`candidate_intelligence/nodes/resume_parser.py`'s note on why) — the three downstream
nodes fan out from here in parallel in the same superstep.
"""

import asyncio

from services.agents.candidate_intelligence.state import CareerGuidanceState
from services.agents.candidate_intelligence.tools.skill_gap import analyze_skill_gaps


async def run(state: CareerGuidanceState) -> dict:
    # Does several CPU-bound model.encode() calls plus blocking Qdrant round trips —
    # keep it off the event loop.
    result = await asyncio.to_thread(
        analyze_skill_gaps, state.get("candidate_skills") or [], state.get("target_role")
    )
    return {
        "resolved_target_role": result.target_role,
        "skill_gaps": result.gaps,
        "covered_skills": result.covered_skills,
    }
