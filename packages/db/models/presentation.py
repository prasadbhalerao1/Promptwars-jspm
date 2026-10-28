import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import Boolean, DateTime, Float, Integer

from packages.db.models.base import Base


class Presentation(Base):
    __tablename__ = "presentations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    file_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("files.id"))
    linked_repo: Mapped[str | None] = mapped_column(Text)
    hackathon_submission_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    problem_statement: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="processing")
    status_detail: Mapped[str | None] = mapped_column(Text)
    uploaded_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "status IN ('processing','done','failed')",
            name="ck_presentations_status",
        ),
    )


class PlagiarismMatch(Base):
    __tablename__ = "plagiarism_matches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    presentation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("presentations.id"), nullable=False)
    matched_presentation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("presentations.id"), nullable=False)
    slide_index: Mapped[int] = mapped_column(Integer, nullable=False)
    similarity: Mapped[float] = mapped_column(Float, nullable=False)
    flagged_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Read on every deck detail view to list that deck's matches.
    __table_args__ = (Index("idx_plagiarism_matches_presentation", "presentation_id"),)


class PresentationScore(Base):
    __tablename__ = "presentation_scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    presentation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("presentations.id"), nullable=False)
    problem_statement: Mapped[str | None] = mapped_column(Text)
    requirement_coverage: Mapped[list | None] = mapped_column(JSONB)
    rubric_breakdown: Mapped[dict | None] = mapped_column(JSONB)
    innovation_score: Mapped[float | None] = mapped_column(Float)
    technical_feasibility_score: Mapped[float | None] = mapped_column(Float)
    presentation_quality_score: Mapped[float | None] = mapped_column(Float)
    business_potential_score: Mapped[float | None] = mapped_column(Float)
    overall_pitch_score: Mapped[float | None] = mapped_column(Float)
    renormalized_scores: Mapped[list | None] = mapped_column(JSONB)
    summary: Mapped[str | None] = mapped_column(Text)
    suggestions: Mapped[list | None] = mapped_column(JSONB)
    ai_content_signal: Mapped[dict | None] = mapped_column(JSONB)
    # Whether the plagiarism check actually ran. Defaults true so existing rows keep
    # their current meaning; only a genuinely failed check writes false.
    plagiarism_checked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    computed_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_presentation_scores_presentation_time", "presentation_id", "computed_at"),
    )


class Slide(Base):
    __tablename__ = "slides"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    presentation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("presentations.id"), nullable=False)
    slide_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    has_image: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    ocr_text: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("idx_slides_presentation_index", "presentation_id", "slide_index"),
    )
