"""Request/response shapes for `POST /supervisor/route` — see
`services/agents/supervisor/graph.py` for the graph this backs."""

from uuid import UUID

from pydantic import BaseModel


class SupervisorRouteRequest(BaseModel):
    raw_request: str
    candidate_id: UUID | None = None
    job_id: UUID | None = None


class SupervisorRouteResponse(BaseModel):
    intent: str | None
    result: dict | None
    error: str | None
