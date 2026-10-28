from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

APPLICATION_STAGES = (
    "sourced",
    "screened",
    "interview_scheduled",
    "offered",
    "rejected",
    "hired",
)


class JobCreateRequest(BaseModel):
    title: str
    description: str
    required_skills: list[str] = []
    min_experience_years: int | None = None
    location: str | None = None
    is_remote: bool = True


class JobResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    organization_id: UUID | None
    posted_by_user_id: UUID
    title: str
    description: str
    required_skills: list[str] | None
    min_experience_years: int | None
    location: str | None
    is_remote: bool
    created_at: datetime
    matching_status: str
    matching_error: str | None


class ApplicationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    job_id: UUID
    candidate_id: UUID
    stage: str
    source: str | None
    applied_at: datetime
    stage_updated_at: datetime


class ApplicationWithJobResponse(ApplicationResponse):
    """Used by GET /candidates/me/applications — the candidate's own view needs the
    job title/company context, not just the raw application row."""

    job_title: str
    job_location: str | None


class ApplicationWithCandidateResponse(ApplicationResponse):
    """Used by the recruiter-facing GET /applications (kanban board) — needs enough
    candidate identity to render a card without a second round-trip per card."""

    candidate_headline: str | None
    candidate_github_username: str | None
    candidate_overall_talent_score: float | None
    # Additive — QA finding "Recruiter #4": doc 06's display-only fraud indicator never
    # existed anywhere in the recruiter-facing API. Read-only lookup against Module 06's
    # `fraud_flags` (never written to here) — the most severe non-dismissed flag's status
    # for this candidate ("upheld" > "under_review" > "raised"), or None if the candidate
    # has no open flag. Display-only: never used to filter/sort/affect ranking anywhere.
    fraud_flag_status: str | None = None
    # Additive — QA finding "Recruiter #3": no click-path from a kanban card to that
    # candidate's actual report. Read-only lookups against Module 03's tables (never
    # written to here); each is the candidate's most recent report of that type, or None
    # if they don't have one yet. The frontend links to whichever is non-null.
    latest_submission_id: UUID | None = None
    latest_interview_session_id: UUID | None = None
    latest_contribution_repo_full_name: str | None = None


class ApplicationStageUpdateRequest(BaseModel):
    stage: str


class MatchScoreResponse(BaseModel):
    """FR-2 — doc/multi-agent-architecture/08 §2's 4-term formula, always shown to
    recruiters as this breakdown, never a bare percentage (doc 08/09 NFR)."""

    model_config = {"from_attributes": True}

    id: UUID
    job_id: UUID
    candidate_id: UUID
    match_percentage: float | None
    skill_similarity: float | None
    semantic_similarity: float | None
    experience_match: float | None
    talent_score_alignment: float | None
    project_relevance: float | None
    explanation: str | None
    computed_at: datetime


class MatchScoreWithCandidateResponse(MatchScoreResponse):
    """The ranked-matches list needs enough candidate identity to render a card —
    joined in by the router, not stored redundantly on match_scores itself."""

    candidate_headline: str | None
    candidate_location: str | None
    candidate_github_username: str | None
    candidate_overall_talent_score: float | None
    # Additive — QA finding "Recruiter #4" names both response schemas explicitly.
    # Same read-only, display-only fraud lookup as ApplicationWithCandidateResponse.
    fraud_flag_status: str | None = None


# --- FR-3: Recruiter AI Copilot ---


class CopilotQueryRequest(BaseModel):
    conversation_id: UUID | None = None  # None starts a new conversation
    message: str


class CopilotResult(BaseModel):
    candidate_id: UUID
    match_percentage: float | None
    explanation: str


class CopilotQueryResponse(BaseModel):
    conversation_id: UUID
    results: list[CopilotResult]
    structured_filters_used: dict


# --- FR-4: Hiring Analytics Dashboard ---


class FunnelStage(BaseModel):
    stage: str
    count: int
    conversion_rate_from_previous: float | None  # None for the first stage


class HiringFunnelResponse(BaseModel):
    job_id: UUID | None  # None when aggregated across all of a recruiter's jobs
    stages: list[FunnelStage]


class TimeToHireResponse(BaseModel):
    job_id: UUID | None
    # Bucketed histogram — {"0-7d": n, "8-14d": n, ...} — never raw per-candidate
    # timestamps in an aggregate analytics endpoint.
    distribution: dict[str, int]
    median_days: float | None


class SourceBreakdownResponse(BaseModel):
    job_id: UUID | None
    direct: int
    copilot_search: int
    hackathon: int
