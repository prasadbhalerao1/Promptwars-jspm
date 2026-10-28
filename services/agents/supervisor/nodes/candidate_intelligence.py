"""Dispatches the supervisor's `candidate_score` intent to Module 01 (Candidate
Intelligence) — reuses the exact response-shaping function
(`services.api.modules.candidates.router._to_score_response`) the real `GET /candidates/me/score`
endpoint calls, plus the same `TalentScore` query, rather than re-deriving the shape or
issuing an HTTP call back into this same API process.

The live `AsyncSession` is read from `config["configurable"]["db"]` (LangGraph's
per-invocation `RunnableConfig`), not from `state` — see `graph.py`'s module docstring for
why.
"""

import uuid

from langchain_core.runnables import RunnableConfig
from sqlalchemy import select

from packages.db.models import TalentScore
from services.agents.supervisor.state import SupervisorState
from services.api.modules.candidates.router import _to_score_response


async def run(state: SupervisorState, config: RunnableConfig) -> dict:
    db = config["configurable"]["db"]
    candidate_id = state.get("candidate_id")
    if not candidate_id:
        return {"error": "candidate_id is required for the candidate_score intent", "result": None}

    try:
        candidate_uuid = uuid.UUID(candidate_id)
    except (ValueError, TypeError):
        # The guard above returns a clean {"error": ...} for a *missing* id; a malformed
        # one raised ValueError out of the node instead. Same class of bad input, so it
        # gets the same handling rather than a 500.
        return {"error": f"candidate_id {candidate_id!r} is not a valid UUID", "result": None}

    result = await db.execute(
        select(TalentScore)
        .where(TalentScore.candidate_id == candidate_uuid)
        .order_by(TalentScore.computed_at.desc())
        .limit(1)
    )
    score = result.scalar_one_or_none()
    if score is None:
        return {
            "result": {
                "module": "candidate_intelligence",
                "candidate_id": candidate_id,
                "talent_score": None,
                "message": "no talent score computed yet for this candidate",
            }
        }
    return {
        "result": {
            "module": "candidate_intelligence",
            "candidate_id": candidate_id,
            "talent_score": _to_score_response(score).model_dump(mode="json"),
        }
    }
