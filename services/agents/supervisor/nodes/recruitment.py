"""Dispatches the supervisor's `job_match` intent to Module 02 (Recruitment) — reuses the
exact service function (`services.api.modules.recruitment.router._run_matching_and_persist`) the
real `GET /jobs/{id}/matches?recompute=true` endpoint calls, running Flow B's real matching
graph in-process against the job's live DB row (real candidate pool, real persisted
`match_scores`), not a mock.

The live `AsyncSession` is read from `config["configurable"]["db"]`, not from `state` —
see `graph.py`'s module docstring for why.
"""

import uuid

from langchain_core.runnables import RunnableConfig
from sqlalchemy import select

from packages.db.models import Job
from services.agents.recruitment.tools.embeddings import RecruitmentUnavailable
from services.agents.supervisor.state import SupervisorState
from services.api.modules.recruitment.router import _run_matching_and_persist


async def run(state: SupervisorState, config: RunnableConfig) -> dict:
    db = config["configurable"]["db"]
    job_id = state.get("job_id")
    if not job_id:
        return {"error": "job_id is required for the job_match intent", "result": None}

    try:
        job_uuid = uuid.UUID(job_id)
    except (ValueError, TypeError):
        return {"error": f"job_id {job_id!r} is not a valid UUID", "result": None}

    result = await db.execute(select(Job).where(Job.id == job_uuid))
    job = result.scalar_one_or_none()
    if job is None:
        return {"error": f"job {job_id} not found", "result": None}

    try:
        rows = await _run_matching_and_persist(db, job)
    except RecruitmentUnavailable as exc:
        return {"error": str(exc), "result": None}

    top = sorted(rows, key=lambda r: r.match_percentage, reverse=True)[:5]
    return {
        "result": {
            "module": "recruitment",
            "job_id": job_id,
            "match_count": len(rows),
            "top_matches": [
                {
                    "candidate_id": str(r.candidate_id),
                    "match_percentage": r.match_percentage,
                    "explanation": r.explanation,
                }
                for r in top
            ],
        }
    }
