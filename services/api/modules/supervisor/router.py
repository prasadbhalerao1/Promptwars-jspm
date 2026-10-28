"""
Supervisor Controller.
Handles Multi-Agent Orchestration Routing.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import CandidateProfile, User
from packages.shared_schemas.supervisor import SupervisorRouteRequest, SupervisorRouteResponse
from services.agents.supervisor.graph import get_graph
from services.agents.supervisor.state import SupervisorState
from services.agents.supervisor.tools.classifier_llm import SupervisorUnavailable
from services.api.core.db import get_db
from services.api.core.rbac import get_current_user
from services.api.modules.recruitment.router import _job_owned_by

router = APIRouter(tags=["Multi-Agent Supervisor"])


async def _authorize_subjects(db: AsyncSession, body: SupervisorRouteRequest, user: User) -> None:
    """Apply the owning module's access rule to whichever subject the caller named.

    This endpoint dispatches into the real Module 01/02 service functions — the
    `candidate_score` node reads any `TalentScore` by candidate id, and the `job_match`
    node runs `_run_matching_and_persist` against any `Job` row. Both took their subject
    id straight from the request body behind nothing but `get_current_user`, so any
    signed-in user could read any candidate's Talent Score, and could make a *write* run
    (matching persists `match_scores`) against a recruiter's job they have no
    relationship to — routing around `_job_owned_by`, which every real recruitment route
    goes through.

    Checking here rather than inside the graph nodes keeps the nodes DB-shaped and
    caller-agnostic, and matches where the rest of this codebase puts authorization: in
    the router, before any pipeline starts.
    """
    if body.job_id is not None:
        if user.role != "recruiter":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="not_your_job_posting"
            )
        await _job_owned_by(db, body.job_id, user)

    if body.candidate_id is not None:
        # Recruiters and admins legitimately look up candidates they are evaluating;
        # a candidate may only ask about themselves.
        if user.role in {"recruiter", "admin"}:
            return
        profile = (
            await db.execute(
                select(CandidateProfile).where(CandidateProfile.id == body.candidate_id)
            )
        ).scalar_one_or_none()
        if profile is None or profile.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="cannot_route_for_other_candidates",
            )


@router.post("/supervisor/route", response_model=SupervisorRouteResponse)
async def route_request(
    body: SupervisorRouteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SupervisorRouteResponse:
    await _authorize_subjects(db, body, user)

    initial_state: SupervisorState = {
        "raw_request": body.raw_request,
        "candidate_id": str(body.candidate_id) if body.candidate_id else None,
        "job_id": str(body.job_id) if body.job_id else None,
        "intent": None,
        "result": None,
        "error": None,
    }
    try:
        result_state = await get_graph().ainvoke(initial_state, config={"configurable": {"db": db}})
    except SupervisorUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return SupervisorRouteResponse(
        intent=result_state.get("intent"),
        result=result_state.get("result"),
        error=result_state.get("error"),
    )
