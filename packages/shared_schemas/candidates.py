from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

SUB_SCORE_NAMES = (
    "coding_ability",
    "problem_solving",
    "project_quality",
    "innovation",
    "technical_consistency",
    "community_participation",
    "leadership",
    "open_source_contributions",
    "hackathon_performance",
    "verified_credentials",
)


class SubScore(BaseModel):
    value: float | None  # 0-100, None when not yet computable (cold start)
    evidence: list[str] = []  # source URLs / repos / identifiers
    rationale: str | None = None
    # Versioned Competency Assessment metadata (v2.0)
    status: str = "supported"  # supported | partially_supported | insufficient_evidence | not_assessed
    rubric_level: str | None = None
    indicators: list[str] = []
    missing_evidence: list[str] = []
    limitations: list[str] = []
    evidence_coverage: float = 0.0
    provenance_items: list[dict] = []


class HackathonExperienceEntry(BaseModel):
    """Self-reported hackathon experience for external hackathons."""

    id: str | None = None  # generated on server
    name: str
    result: str  # winner | top5 | finalist | participant
    weight: float  # 1-5 importance/prestige scaling
    date: str  # ISO 8601 date
    platform_hackathon_id: str | None = None  # null for external hackathons


class HackathonExperienceRequest(BaseModel):
    """Request to add/update hackathon experience."""

    name: str
    result: str  # winner | top5 | finalist | participant
    weight: float
    date: str


def _stats_refresh_cooldown_seconds() -> int:
    """Read the cooldown from Settings at response-construction time.

    Imported lazily inside the function on purpose: this package is deliberately free of
    service-layer dependencies so the agents and the schema codegen can import it without
    pulling in FastAPI settings. A module-level import would invert that.
    """
    from services.api.core.config import get_settings

    return get_settings().stats_refresh_cooldown_minutes * 60


class EvidenceConfidence(BaseModel):
    """How much of the Talent Score is backed by real evidence vs. cold-start gaps.

    available_signals / expected_signals, where "signals" are the 7 sub-scores that
    resolved to a non-None value. Recruiters should treat scores below the 50%
    confidence threshold as based on a sparse profile, not a weak candidate.
    """

    available_signals: int
    expected_signals: int
    confidence: float  # available_signals / expected_signals, 0-1


class CandidateProfileResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    user_id: UUID
    full_name: str | None = None
    github_username: str | None
    leetcode_username: str | None
    headline: str | None
    location: str | None
    skills: list[dict] | None
    experience: list[dict] | None
    education: list[dict] | None
    merged_conflicts: list[dict] | None
    hackathon_experience: list[dict] | None = None
    username: str | None
    portfolio_published: bool
    github_stats: dict | None
    leetcode_stats: dict | None
    stats_refreshed_at: datetime | None
    # Published so the client can render the refresh countdown without hardcoding the
    # cooldown. It is env-tunable (`STATS_REFRESH_COOLDOWN_MINUTES`), so a client-side
    # copy silently disagrees with the API the moment a deployment changes it — enabling
    # the button early and earning a 429.
    stats_refresh_cooldown_seconds: int = Field(
        default_factory=_stats_refresh_cooldown_seconds
    )
    ingestion_status: str
    ingestion_error: str | None
    updated_at: datetime


class LeetcodeConnectRequest(BaseModel):
    leetcode_username: str


class GithubConnectRequest(BaseModel):
    github_username: str


class ConflictResolution(BaseModel):
    field: str
    resolved_value: str


class TalentScoreResponse(BaseModel):
    overall: float | None
    sub_scores: dict[str, SubScore]
    renormalized_subscores: list[str]
    confidence: EvidenceConfidence
    score_version: str
    computed_at: datetime


class BadgeResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    skill_name: str
    corroboration_sources: list[str]
    awarded_at: datetime


class GithubIngestRequest(BaseModel):
    github_username: str


class PublicPortfolioProject(BaseModel):
    repo_full_name: str
    stars: int | None
    forks: int | None
    languages: dict | None
    topics: list[str] | None = None
    pushed_at: datetime | None = None
    description: str | None = None
    commit_count: int | None = None
    pr_count: int | None = None
    issue_count: int | None = None


class GithubSummary(BaseModel):
    total_stars: int
    total_commits: int
    total_prs: int
    total_issues: int
    total_forks: int
    # From candidate.github_stats (services/agents/candidate_intelligence/tools/github.py
    # GithubAnalysis, merged in during ingestion) — 0 until a candidate has connected
    # GitHub and run ingestion at least once, not a sentinel for "no data".
    owned_repo_count: int
    external_contributions: int
    pr_review_count: int
    projects: list[PublicPortfolioProject]


class DashboardResponse(BaseModel):
    profile: CandidateProfileResponse
    latest_score: TalentScoreResponse | None
    score_history: list[TalentScoreResponse]
    badges: list[BadgeResponse]
    github_summary: GithubSummary


# --- FR-5: AI Resume & Portfolio Builder ---


class FactCheckFinding(BaseModel):
    """One claim the Fact-Check Agent checked in a generated document."""

    claim: str
    supported: bool
    note: str | None = None


class ResumeGenerateRequest(BaseModel):
    # FR-5.4: when set, bullets are re-ranked/re-worded to emphasize this JD's
    # keywords — still grounded only in the candidate's actual profile data.
    target_job_description: str | None = None


class CoverLetterGenerateRequest(BaseModel):
    # FR-5.3: cover letters are always parameterized by a target JD.
    target_job_description: str


class GeneratedDocumentResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    document_type: str  # "resume" | "cover_letter"
    target_job_description: str | None
    content: dict
    file_url: str | None = None
    fact_check_status: str  # "pending" | "passed" | "failed"
    fact_check_findings: list[FactCheckFinding] | None
    model_used: str | None
    generated_at: datetime


class PortfolioPublishRequest(BaseModel):
    # Optional after onboarding: if the candidate already has a username slug set,
    # a bare publish toggle doesn't need to re-supply it.
    username: str | None = None


class ProfileUpdateRequest(BaseModel):
    """PATCH /candidates/me — all fields optional; only supplied fields are applied."""
    full_name: str | None = None
    username: str | None = None
    headline: str | None = None
    location: str | None = None
    college: str | None = None
    degree: str | None = None


class PublicPortfolioResponse(BaseModel):
    """FR-5.2 — payload for the public, unauthenticated, SSR `/[username]` route.
    Read-only, no PII beyond what the candidate chose to publish (no email/user_id)."""

    username: str
    headline: str | None
    location: str | None
    skills: list[dict] | None
    experience: list[dict] | None
    education: list[dict] | None
    hackathon_experience: list[dict] | None = None
    projects: list[PublicPortfolioProject]
    badges: list[BadgeResponse]
    overall_score: float | None
    # Evidence Confidence for that score: signals with evidence / signals expected.
    confidence_available_signals: int | None = None
    confidence_expected_signals: int | None = None
    # Codolio-style split: Development Stats (GitHub calendar/streak/languages) and
    # Problem Solving Stats (LeetCode). Both are cached snapshots (candidate.github_stats /
    # .leetcode_stats), never fetched live on a public page view.
    github_username: str | None
    leetcode_username: str | None
    github_stats: dict | None
    github_summary: GithubSummary
    leetcode_stats: dict | None
    stats_refreshed_at: datetime | None
    updated_at: datetime


# --- FR-4: AI Career Guidance System ---


class CareerGuidanceResponse(BaseModel):
    """FR-4.1-4.5. `salary_estimate_low`/`salary_estimate_high` are a range only —
    never a point estimate (doc 01 §8) — and are `None` together when no Talent Score
    or no trained salary model is available yet (cold start, not fabrication)."""

    target_role: str | None
    skill_gaps: list[dict]  # [{skill, similarity, weight, priority}], worst gap first
    recommended_courses: list[dict]  # course_catalog rows matched to the gaps above
    roadmap: dict  # {"stages": [{"stage","skills","estimated_weeks","description"}]}
    salary_estimate_low: int | None
    salary_estimate_high: int | None
    salary_rationale: str | None = None
    generated_at: datetime
