from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel

INGESTION_MODES = ("manual_csv", "webhook", "direct")
HACKATHON_STATUSES = ("draft", "active", "judging", "finalized")


class HackathonCreateRequest(BaseModel):
    name: str
    start_date: date | None = None
    end_date: date | None = None
    tracks: list[str] = []
    ingestion_mode: str = "direct"


class HackathonResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    organizer_org_id: UUID | None
    organizer_user_id: UUID
    name: str
    start_date: date | None
    end_date: date | None
    tracks: list[str] | None
    ingestion_mode: str
    status: str
    created_at: datetime


# --- FR-7: Ingestion ---


class TeamMemberInput(BaseModel):
    """One roster row. `candidate_id` is resolved server-side by matching
    `github_username` against `candidate_profiles` — a CSV/webhook roster member who isn't
    a platform candidate yet still gets a row (see `HackathonTeamMember`'s docstring)."""

    github_username: str | None = None
    display_name: str | None = None
    role: str = "member"


class TeamSubmissionInput(BaseModel):
    """Common normalized shape for all three FR-7 ingestion paths — CSV rows (already
    mapped client-side by the SheetJS preview grid), webhook payloads (mapped
    server-side by the Normalization Agent), and direct in-platform submission (entered
    through this platform's own form, no mapping needed)."""

    team_name: str
    track: str | None = None
    members: list[TeamMemberInput] = []
    repo_url: str | None = None
    presentation_id: UUID | None = None  # already uploaded via POST /presentations/upload
    judge_score: float | None = None  # organizer CSV/webhook may already carry a judge score


class CSVImportRequest(BaseModel):
    """Organizer manual CSV/XLSX upload (FR-7a), pre-parsed client-side (SheetJS, doc 05
    §8's `CSVImportPreview.tsx`) into rows before this call — the backend still validates
    the resulting shape and reports per-row errors, satisfying the doc's "preview/diff
    before committing" NFR from the SheetJS-rendered preview grid rather than a second
    backend round trip."""

    teams: list[TeamSubmissionInput]


class CSVImportRowError(BaseModel):
    row_index: int
    team_name: str | None
    error: str


class CSVImportResponse(BaseModel):
    teams_created: int
    members_created: int
    row_errors: list[CSVImportRowError]


# Webhook ingestion (FR-7b) accepts an arbitrary `dict` body — an external platform's raw
# payload shape, not this platform's schema — and runs it through the Normalization
# Agent (`services/agents/hackathon/tools/normalization.py`) to produce a
# `TeamSubmissionInput` server-side, unlike CSV/direct which are already structured.

# --- Teams / Submissions ---


class TeamMemberResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    candidate_id: UUID | None
    github_username: str | None
    display_name: str | None
    role: str


class TeamResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    hackathon_id: UUID
    team_name: str
    track: str | None


class SubmissionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    team_id: UUID
    repo_url: str | None
    presentation_id: UUID | None
    repo_analysis_submission_id: UUID | None
    judge_score: float | None
    judge_rationale: str | None
    submitted_at: datetime


class TeamDetailResponse(BaseModel):
    team: TeamResponse
    members: list[TeamMemberResponse]
    submission: SubmissionResponse | None
    ranking: "RankingResponse | None" = None


class JudgeQueueEntry(BaseModel):
    submission_id: UUID
    hackathon_id: UUID
    hackathon_name: str
    team_id: UUID
    team_name: str
    repo_url: str | None
    presentation_id: UUID | None
    judge_score: float | None
    judge_rationale: str | None


class JudgeScoreRequest(BaseModel):
    """Additive endpoint (not in either doc's API list) — FR-2's "judge scores
    submissions" needs a write path and the frontend judge rubric page
    (`(judge)/submissions/[id]`) already collects both fields; see `.agents/decisions.md`.
    """

    score: float
    rationale: str | None = None


# --- Rankings ---


class ScoreBreakdown(BaseModel):
    judge_score_component: float | None
    pitch_score_component: float | None
    repo_quality_component: float | None
    novelty_component: float | None
    renormalized: list[str]  # which components were N/A and re-normalized away


class RankingResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    hackathon_id: UUID
    team_id: UUID
    team_name: str | None = None
    rank: int
    composite_score: float
    score_breakdown: dict | None
    finalized_at: datetime


class ScoringWeightsConfig(BaseModel):
    judge_weight: float = 0.25
    pitch_weight: float = 0.25
    repo_weight: float = 0.25
    novelty_weight: float = 0.25


class FinalizeRankingsRequest(BaseModel):
    custom_weights: ScoringWeightsConfig | None = None


class FinalizeRankingsResponse(BaseModel):
    hackathon_id: UUID
    # "processing" — finalization now runs as a background task, so `rankings` here is
    # whatever was already persisted (empty on a first run), NOT the result of this run.
    # Poll GET /hackathons/{id}/rankings/status and re-fetch the rankings once done.
    ranking_status: str
    rankings: list[RankingResponse]


# --- Recruiter access ---


class WatchlistCreateRequest(BaseModel):
    track: str | None = None
    min_rank: int | None = None
    skills: list[str] = []


class WatchlistResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    recruiter_id: UUID
    criteria: dict | None
    created_at: datetime


class TopPerformerEntry(BaseModel):
    hackathon_id: UUID
    hackathon_name: str
    team_id: UUID
    team_name: str
    rank: int
    composite_score: float
    candidate_id: UUID | None
    candidate_headline: str | None
    candidate_github_username: str | None
    # Phase 2 integration (services/api/core/event_consumer.py) — live-computed against
    # this recruiter's recruiter_watchlists, not persisted. False/[] for every entry when
    # the recruiter has no watchlists yet (same "never empty" fallback the feed always had).
    matched_watchlist: bool = False
    match_reasons: list[str] = []


class TopPerformersFeedResponse(BaseModel):
    entries: list[TopPerformerEntry]
