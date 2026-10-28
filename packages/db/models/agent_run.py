import uuid

from sqlalchemy import Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime

from packages.db.models.base import Base


class AgentRun(Base):
    """Explainability record — every AI score/verdict must have one (constraints.md §4)."""

    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_name: Mapped[str] = mapped_column(Text, nullable=False)
    subject_type: Mapped[str] = mapped_column(Text, nullable=False)  # candidate | presentation | application | ...
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    input_ref: Mapped[dict | None] = mapped_column(JSONB)
    output: Mapped[dict | None] = mapped_column(JSONB)
    model_used: Mapped[str | None] = mapped_column(Text)
    langfuse_trace_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        # Provenance lookups are always "all runs for this subject" — every ingestion,
        # scoring pass and fraud check appends here, so an unindexed table meant a
        # sequential scan that grew with total platform activity.
        Index("idx_agent_runs_subject", "subject_type", "subject_id"),
    )
