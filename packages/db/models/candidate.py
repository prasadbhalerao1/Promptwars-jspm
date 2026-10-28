import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import Boolean, DateTime, Float, Integer

from packages.db.models.base import Base


class CandidateProfile(Base):
    """Module 1 (Candidate Intelligence) — canonical merged profile.

    Schema follows doc/multi-agent-architecture/01 §7 (adds `score_version`-adjacent
    provenance via merged_conflicts) over doc/SRS/01 §5.
    """

    __tablename__ = "candidate_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    github_username: Mapped[str | None] = mapped_column(Text)
    # Codolio-style "Development Stats" (GitHub calendar/streak/languages, GraphQL-sourced
    # — see services/agents/candidate_intelligence/tools/github_calendar.py) and "Problem
    # Solving Stats" (LeetCode, tools/leetcode.py). Cached rather than fetched live on
    # every profile view: both are third-party calls with their own rate limits, so the
    # public portfolio page reads from these columns and a candidate-triggered refresh
    # (cooldown-gated, POST /candidates/me/stats/refresh) repopulates them.
    leetcode_username: Mapped[str | None] = mapped_column(Text)
    github_stats: Mapped[dict | None] = mapped_column(JSONB)
    leetcode_stats: Mapped[dict | None] = mapped_column(JSONB)
    stats_refreshed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    headline: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    skills: Mapped[list | None] = mapped_column(JSONB)  # [{name, source, confidence}]
    experience: Mapped[list | None] = mapped_column(JSONB)
    education: Mapped[list | None] = mapped_column(JSONB)
    merged_conflicts: Mapped[list | None] = mapped_column(JSONB)
    # Hackathon experience (self-reported) — list of external hackathons the candidate won/placed in.
    # [{id, name, result, weight, date, platform_hackathon_id}], where result is one of
    # winner|top5|finalist|participant, weight is 1-5 importance, platform_hackathon_id is null
    # for external hackathons (platform-run ones are queried separately via HackathonRanking).
    hackathon_experience: Mapped[list | None] = mapped_column(JSONB)
    # FR-5.2 public portfolio (`/[username]`) — neither doc set names a slug column, but
    # the SSR route can't exist without one. Nullable + unique: no username until the
    # candidate opts in via POST /candidates/me/portfolio/publish.
    username: Mapped[str | None] = mapped_column(Text, unique=True)
    portfolio_published: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    # Ingestion (resume/certificate/GitHub OAuth) now runs as a FastAPI BackgroundTask
    # instead of inline in the request — the endpoint returns immediately and the
    # frontend polls GET /candidates/me/ingestion-status until this leaves "processing".
    ingestion_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="idle")
    ingestion_error: Mapped[str | None] = mapped_column(Text)
    # Which phase the running pipeline is in, for the stepwise progress UI. The whole run
    # can take minutes on a large GitHub account, and a single unchanging "analyzing…"
    # message for that long is indistinguishable from a hang — which is exactly how it
    # was reported. Written by `_run_ingestion_and_persist` as each phase starts, so it
    # reflects real progress rather than an animation on a timer.
    ingestion_stage: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", lazy="joined")

    @property
    def full_name(self) -> str | None:
        return self.user.full_name if self.user else None


class GithubSnapshot(Base):
    __tablename__ = "github_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id"), nullable=False
    )
    repo_full_name: Mapped[str] = mapped_column(Text, nullable=False)
    stars: Mapped[int | None] = mapped_column(Integer)
    forks: Mapped[int | None] = mapped_column(Integer)
    commit_count: Mapped[int | None] = mapped_column(Integer)
    pr_count: Mapped[int | None] = mapped_column(Integer)
    issue_count: Mapped[int | None] = mapped_column(Integer)
    languages: Mapped[dict | None] = mapped_column(JSONB)
    is_fork: Mapped[bool | None] = mapped_column(Boolean)
    # Repository analytics dashboard (Skills section categorization, "recently updated"
    # sort) — GitHub REST `topics`/`pushed_at`, additive to the original doc 01 schema.
    topics: Mapped[list | None] = mapped_column(JSONB)
    pushed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    description: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Scanned on every candidate dashboard load, the public portfolio, /me/github-summary,
    # and (IN-filtered over the whole candidate set) on every recruiter candidate-pool
    # build — this was a sequential scan on all of those paths.
    __table_args__ = (Index("idx_github_snapshots_candidate", "candidate_id"),)


class Certification(Base):
    __tablename__ = "certifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id"), nullable=False
    )
    file_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("files.id"))
    issuer: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    issue_date: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    credential_id: Mapped[str | None] = mapped_column(Text)
    ocr_confidence: Mapped[float | None] = mapped_column(Float)
    verification_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="unverified")

    __table_args__ = (
        CheckConstraint(
            "verification_status IN ('unverified','pending','verified','rejected')",
            name="ck_certifications_verification_status",
        ),
        # Certificates are always listed per candidate.
        Index("idx_certifications_candidate_id", "candidate_id"),
    )


class TalentScore(Base):
    __tablename__ = "talent_scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id"), nullable=False
    )
    coding_ability: Mapped[float | None] = mapped_column(Float)
    project_quality: Mapped[float | None] = mapped_column(Float)
    leadership: Mapped[float | None] = mapped_column(Float)
    problem_solving: Mapped[float | None] = mapped_column(Float)
    innovation: Mapped[float | None] = mapped_column(Float)
    community_participation: Mapped[float | None] = mapped_column(Float)
    technical_consistency: Mapped[float | None] = mapped_column(Float)
    open_source_contributions: Mapped[float | None] = mapped_column(Float)
    hackathon_performance: Mapped[float | None] = mapped_column(Float)
    overall: Mapped[float | None] = mapped_column(Float)
    # Which sub-scores were N/A and had their weight re-normalized away (doc 08 §1.1) —
    # part of the provenance trail, never a silent adjustment.
    renormalized_subscores: Mapped[list | None] = mapped_column(JSONB)
    # Evidence Confidence Score (Talent Score v2) — available_signals/expected_signals,
    # surfaced so recruiters can tell a low score from a low-evidence score apart.
    confidence_available_signals: Mapped[int | None] = mapped_column(Integer)
    confidence_expected_signals: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float | None] = mapped_column(Float)
    score_version: Mapped[str] = mapped_column(Text, nullable=False, server_default="v1")
    computed_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("idx_scores_candidate_time", "candidate_id", "computed_at"),)


class Badge(Base):
    __tablename__ = "badges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id"), nullable=False
    )
    skill_name: Mapped[str] = mapped_column(Text, nullable=False)
    corroboration_sources: Mapped[list] = mapped_column(JSONB, nullable=False)
    awarded_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Same hot paths as github_snapshots above (dashboard, badges list, candidate-pool
    # build) — previously unindexed.
    __table_args__ = (Index("idx_badges_candidate", "candidate_id"),)


class GeneratedDocument(Base):
    """Module 1 FR-5 (Resume & Portfolio Builder) — one row per resume/cover-letter
    generation attempt, covering both FR-5.1/5.3 (plain generation) and FR-5.4
    (JD-optimized: `target_job_description` set, generated bullets re-ranked/re-worded
    to that JD). Neither doc set specifies a table for this — added additively, same
    reasoning as `career_recommendations` in doc 01 §7 (one row per on-demand generation,
    not a mutable "current resume" singleton, so candidates keep a history).

    `fact_check_status`/`fact_check_findings` implement the mandatory Fact-Check Agent
    guardrail (doc 01 §4, NFR "zero tolerance for fabricated experience") — every row is
    written regardless of pass/fail for the explainability trail, but the API only ever
    hands a candidate a `failed` row's PDF/text if generation is being deliberately
    disclosed as unresolved; see `services/api/routers/candidates.py` (FactCheckFailed).
    """

    __tablename__ = "generated_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id"), nullable=False
    )
    document_type: Mapped[str] = mapped_column(Text, nullable=False)  # resume | cover_letter
    target_job_description: Mapped[str | None] = mapped_column(Text)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    file_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("files.id"))
    fact_check_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    fact_check_findings: Mapped[list | None] = mapped_column(JSONB)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    model_used: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "document_type IN ('resume','cover_letter')", name="ck_generated_documents_document_type"
        ),
        CheckConstraint(
            "fact_check_status IN ('pending','passed','failed')",
            name="ck_generated_documents_fact_check_status",
        ),
        Index("idx_generated_documents_candidate_time", "candidate_id", "generated_at"),
    )


class CourseCatalogEntry(Base):
    """FR-4.2/FR-4.5 — curated, statically-seeded course catalog (doc 01 §8: "maintained
    static table ... not scraped live"). Seed rows are inserted by this table's own
    migration, not by application code."""

    __tablename__ = "course_catalog"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(Text, nullable=False)  # coursera | freecodecamp | vendor
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    skill_tags: Mapped[list] = mapped_column(JSONB, nullable=False)  # ["python", "system-design", ...]
    level: Mapped[str | None] = mapped_column(Text)  # beginner | intermediate | advanced
    estimated_hours: Mapped[int | None] = mapped_column(Integer)
    is_free: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "provider IN ('coursera','freecodecamp','vendor')", name="ck_course_catalog_provider"
        ),
        CheckConstraint(
            "level IS NULL OR level IN ('beginner','intermediate','advanced')",
            name="ck_course_catalog_level",
        ),
    )


class CareerRecommendation(Base):
    """FR-4 — AI Career Guidance System output (doc/multi-agent-architecture/01 §7).

    `target_role` isn't in the doc's table verbatim — added so a candidate can request
    guidance for more than one target role and each gets its own cached row (see
    .agents/decisions.md dated entry for this module)."""

    __tablename__ = "career_recommendations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id"), nullable=False
    )
    target_role: Mapped[str | None] = mapped_column(Text)
    skill_gaps: Mapped[list | None] = mapped_column(JSONB)
    recommended_courses: Mapped[list | None] = mapped_column(JSONB)
    roadmap: Mapped[dict | None] = mapped_column(JSONB)
    # Range only, never a point estimate (doc 01 §8) — enforced at the tool layer too.
    salary_estimate_low: Mapped[int | None] = mapped_column(Integer)
    salary_estimate_high: Mapped[int | None] = mapped_column(Integer)
    salary_rationale: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_career_recs_candidate_time", "candidate_id", "generated_at"),
    )
