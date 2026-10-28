import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime, Float, Integer, Boolean

from packages.db.models.base import Base


class Assessment(Base):
    """Module 3 (Assessment & Verification) — FR-1. `spec` includes hidden test cases in
    full (candidate must execute them client-side per doc 03 §2's Pyodide-only sandbox
    design) for `type='coding'`, the question bank for `type='mcq'`, or is empty/unused
    for `type='project_analysis'` (that submission is a repo reference, not a spec)."""

    __tablename__ = "assessments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id"))
    # Nullable — an assessment can be authored as a reusable template before it's
    # assigned to any specific candidate (mirrors job_id's own nullability). FKs to
    # candidate_profiles, not users, matching Submission/InterviewSession/
    # ContributionReport's existing convention for every other candidate-scoped column
    # in this module.
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id")
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)
    spec: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("type IN ('coding','mcq','project_analysis')", name="ck_assessments_type"),
        Index("idx_assessments_candidate", "candidate_id"),
    )


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessments.id"), nullable=False
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id"), nullable=False
    )
    code_or_answers: Mapped[dict | None] = mapped_column(JSONB)
    # Pass/fail per hidden test as computed client-side — never the expected values
    # themselves, per doc 03 §2's client-execution design.
    test_results: Mapped[dict | None] = mapped_column(JSONB)
    static_analysis: Mapped[dict | None] = mapped_column(JSONB)
    llm_review: Mapped[dict | None] = mapped_column(JSONB)
    score: Mapped[float | None] = mapped_column(Float)
    # "processing" until the verification graph (static analysis + LLM code review)
    # finishes in the background, then "done" / "failed". Grading previously ran inline
    # in POST /assessments/{id}/submit, holding the candidate's request open for the
    # whole pipeline; the row is now inserted immediately and the client polls.
    grading_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="done")
    grading_error: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_submissions_assessment", "assessment_id"),
        # Talent Score v2's coding_ability/problem_solving pull the candidate's latest
        # submission score directly (services/agents/candidate_intelligence/tools/
        # assessment_bridge.py) — without this, that lookup full-scans the table.
        Index("idx_submissions_candidate", "candidate_id"),
    )


class InterviewSession(Base):
    """A single AI interview run and its turn-by-turn working state."""

    __tablename__ = "interview_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id"), nullable=False
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id"))
    interview_definition_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interview_definitions.id")
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="in_progress")
    # Server-side working state for the turn-based graph (topic_plan, current_topic_idx,
    # per_topic_scores, follow_up_count_this_topic) — no LangGraph checkpointer exists
    # anywhere in this codebase; this is the manual-persistence slot for it, same
    # convention as Module 02's `copilot_conversations.structured_filters`.
    state: Mapped[dict | None] = mapped_column(JSONB)
    started_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status IN ('in_progress','completed','abandoned')", name="ck_interview_sessions_status"
        ),
        # The recruiter attempts list filters the whole table by definition.
        Index("idx_interview_sessions_definition", "interview_definition_id"),
        # A candidate's own session history, and a job's sessions.
        Index("idx_interview_sessions_candidate_id", "candidate_id"),
        Index("idx_interview_sessions_job_id", "job_id"),
    )


class InterviewTranscriptTurn(Base):
    __tablename__ = "interview_transcripts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interview_sessions.id"), nullable=False
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    ts: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("role IN ('agent','candidate')", name="ck_interview_transcripts_role"),
        Index("idx_interview_transcripts_session_turn", "session_id", "turn_index"),
    )


class InterviewReport(Base):
    """`response_confidence_signal` — architecture doc §6's renaming of SRS's
    `confidence_score`, explicitly to make clear it's transcript-derived (hedging
    language, answer specificity/structure), never voice-biometric/emotion inference."""

    __tablename__ = "interview_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interview_sessions.id"), nullable=False
    )
    response_confidence_signal: Mapped[float | None] = mapped_column(Float)
    technical_rating: Mapped[float | None] = mapped_column(Float)
    communication_rating: Mapped[float | None] = mapped_column(Float)
    # Structured rubric scores: {competencies: [{name: str, score: float, feedback: str}]}
    # Maps to InterviewDefinition.scoring_rubric for consistent evaluation
    rubric_scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    hiring_recommendation: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Looked up by session on every report fetch and existence check.
    __table_args__ = (Index("idx_interview_reports_session", "session_id"),)


class InterviewDefinition(Base):
    """Recruiter-authored, reusable interview templates. Each definition specifies a role,
    job description, and expected years of experience; the LLM drafts interview topics from
    this context, and candidates can browse open definitions to self-serve practice interviews."""

    __tablename__ = "interview_definitions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    role_title: Mapped[str] = mapped_column(Text, nullable=False)
    job_description: Mapped[str] = mapped_column(Text, nullable=False)
    years_experience: Mapped[int | None] = mapped_column(Integer)
    questions: Mapped[list] = mapped_column(JSONB, nullable=False)  # [{id: str, topic: str}, ...]
    question_count: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    # Structured scoring rubric: {competencies: [{name: str, description: str, weight: float}], scale: {min: 0, max: 100}}
    # Enables consistent, structured evaluation instead of bare 0-100 scoring
    scoring_rubric: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("idx_interview_definitions_created_by", "created_by_user_id"),)


class ContributionReport(Base):
    """FR-3. `github_username` is additive (neither doc's SQL has it) — a team member
    who isn't yet a platform candidate still needs to show up in the report;
    `candidate_id` stays nullable exactly as both docs' own SQL already has it."""

    __tablename__ = "contribution_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_full_name: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id")
    )
    github_username: Mapped[str | None] = mapped_column(Text)
    contribution_share: Mapped[float | None] = mapped_column(Float)
    commits: Mapped[int | None] = mapped_column(Integer)
    lines_survived: Mapped[int | None] = mapped_column(Integer)
    prs_opened: Mapped[int | None] = mapped_column(Integer)
    prs_reviewed: Mapped[int | None] = mapped_column(Integer)
    anomaly_note: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_contribution_reports_repo", "repo_full_name"),
        Index("idx_contribution_reports_candidate_id", "candidate_id"),
    )
