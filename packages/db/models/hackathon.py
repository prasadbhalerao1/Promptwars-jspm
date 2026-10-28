"""Module 5 (Hackathon-to-Hiring Pipeline) — doc/SRS/05, doc/multi-agent-architecture/05.

Schema follows doc 05 §5 verbatim except for the additive columns documented inline below
(same "additive schema, not in either doc's SQL" pattern already used by every prior
module — see `.agents/decisions.md`'s dated entries for Modules 01-03).

**No `judge_evaluations` table** — this is the one real disagreement between the two doc
sets (`.agents/DOCUMENTATION_MAP.md`'s Known Differences table): the architecture doc adds
a separate `judge_evaluations` table, while SRS keeps a single `judge_score` column on
`hackathon_submissions`. The member-1 assignment file's own data-model list only names
`hackathon_submissions` (no `judge_evaluations`), so the SRS design is what's built here —
logged as this session's resolution of that doc conflict in `.agents/decisions.md`.
"""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import Date, DateTime, Float, Integer

from packages.db.models.base import Base

_INGESTION_MODES = "manual_csv,webhook,direct".split(",")
_HACKATHON_STATUSES = "draft,active,judging,finalized".split(",")


class Hackathon(Base):
    __tablename__ = "hackathons"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organizer_org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id")
    )
    # Additive — neither doc's `hackathons` table names an owning user, but FR-1's
    # organizer-scoped "my hackathons" listing needs one (same role `Job.posted_by_user_id`
    # plays for Module 02's `jobs`, since `organizer_org_id` alone can't scope an organizer
    # with no organization yet).
    organizer_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    start_date: Mapped[object | None] = mapped_column(Date)
    end_date: Mapped[object | None] = mapped_column(Date)
    tracks: Mapped[list | None] = mapped_column(JSONB)  # ["Full-Stack Dev", "ML Algorithms"]
    ingestion_mode: Mapped[str] = mapped_column(Text, nullable=False, server_default="direct")
    # Additive — lifecycle state for the organizer UI (draft -> active -> judging ->
    # finalized). Neither doc has a status column; `hackathon_rankings` rows existing is
    # the doc's only implicit "finalized" signal, but the organizer dashboard needs to
    # render event state before any ranking exists at all.
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="draft")
    # Progress of the ranking-finalization pipeline, tracked separately from `status`
    # above: `status` is the organizer-facing lifecycle (and is CHECK-constrained to
    # draft/active/judging/finalized), whereas this is the async job state for a single
    # finalize run. Finalization (repo verification, novelty search, composite scoring
    # across every team) used to run inline in POST .../rankings/finalize and held the
    # organizer's request open for the whole pipeline; it now runs as a background task
    # and the client polls. Mirrors `Job.matching_status` / `Presentation.status`.
    ranking_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="idle")
    ranking_error: Mapped[str | None] = mapped_column(Text)
    # Configurable ranking weights (JSONB) — organizers can adjust how much each component contributes
    # to the final ranking. Defaults to {judge: 0.40, pitch: 0.30, repo: 0.20, novelty: 0.10}
    scoring_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(f"ingestion_mode IN ({', '.join(repr(m) for m in _INGESTION_MODES)})", name="ck_hackathons_ingestion_mode"),
        CheckConstraint(f"status IN ({', '.join(repr(s) for s in _HACKATHON_STATUSES)})", name="ck_hackathons_status"),
    )


class HackathonTeam(Base):
    __tablename__ = "hackathon_teams"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hackathon_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hackathons.id"), nullable=False
    )
    team_name: Mapped[str] = mapped_column(Text, nullable=False)
    track: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("idx_hackathon_teams_hackathon", "hackathon_id"),)


class HackathonTeamMember(Base):
    """Doc 05 §5 uses a composite `(team_id, candidate_id)` primary key, which requires
    `candidate_id` on every row. A CSV/webhook-imported roster member frequently isn't a
    platform candidate yet (no `users`/`candidate_profiles` row exists to link to) — same
    real gap Module 03's `ContributionReport.github_username` fallback already solved once
    this project. Switched to a surrogate `id` PK with nullable `candidate_id` plus
    `github_username`/`display_name` fallbacks so an unregistered teammate can still appear
    on the roster; `candidate_id` is backfilled later if/when they sign up (matched by
    `github_username`, the same identifier `contribution_reports` already keys on)."""

    __tablename__ = "hackathon_team_members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hackathon_teams.id"), nullable=False
    )
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id")
    )
    github_username: Mapped[str | None] = mapped_column(Text)
    display_name: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, nullable=False, server_default="member")

    __table_args__ = (
        CheckConstraint("role IN ('lead','member')", name="ck_hackathon_team_members_role"),
        Index("idx_hackathon_team_members_team", "team_id"),
        UniqueConstraint("team_id", "candidate_id", name="uq_hackathon_team_members_team_candidate"),
        # The unique constraint's index leads with team_id, so it cannot serve the
        # reverse lookup ("which teams is this candidate on") the candidate view does.
        Index("idx_hackathon_team_members_candidate", "candidate_id"),
    )


class HackathonSubmission(Base):
    __tablename__ = "hackathon_submissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hackathon_teams.id"), nullable=False
    )
    repo_url: Mapped[str | None] = mapped_column(Text)
    presentation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("presentations.id"))
    # Additive — points at the Module 03 `submissions` row (type='project_analysis') this
    # repo was scored by, so ranking reads `Submission.score` straight off that row instead
    # of re-triggering static analysis on every recompute (FR-4/FR-7's "idempotent and
    # re-runnable" NFR).
    repo_analysis_submission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("submissions.id")
    )
    judge_score: Mapped[float | None] = mapped_column(Float)
    # Additive — the judge frontend stub (`(judge)/submissions/[id]`) already collects a
    # qualitative rationale alongside the numeric score; SRS's single `judge_score` column
    # has nowhere else to put it.
    judge_rationale: Mapped[str | None] = mapped_column(Text)
    judge_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    submitted_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_hackathon_submissions_team", "team_id"),
        UniqueConstraint("team_id", name="uq_hackathon_submissions_team"),
    )


class HackathonRanking(Base):
    __tablename__ = "hackathon_rankings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hackathon_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hackathons.id"), nullable=False
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hackathon_teams.id"), nullable=False
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    composite_score: Mapped[float] = mapped_column(Float, nullable=False)
    score_breakdown: Mapped[dict | None] = mapped_column(JSONB)
    finalized_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("hackathon_id", "team_id", name="uq_hackathon_rankings_hackathon_team"),
        Index("idx_hackathon_rankings_hackathon_rank", "hackathon_id", "rank"),
        # Per-team lookups (both constraint indexes above lead with hackathon_id, so
        # neither covers a team_id-only filter) — used when rankings are read back and
        # rewritten on each finalization.
        Index("idx_hackathon_rankings_team", "team_id"),
    )


class RecruiterWatchlist(Base):
    __tablename__ = "recruiter_watchlists"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recruiter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    criteria: Mapped[dict | None] = mapped_column(JSONB)  # {track, min_rank, skills}
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("idx_recruiter_watchlists_recruiter", "recruiter_id"),)
