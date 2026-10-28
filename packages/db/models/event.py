import uuid

from sqlalchemy import Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime

from packages.db.models.base import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # e.g. 'hackathon.rankings.finalized', 'hackathon.submission.scored', 'profile.updated'
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        # Partial index: the consumer polls for unprocessed rows of one event type every
        # 30s forever, and only that subset is ever queried. Keeping it partial means the
        # index stays small as the append-only table grows, since rows drop out of it
        # once processed_at is set.
        Index(
            "idx_events_unprocessed_type",
            "event_type",
            postgresql_where=text("processed_at IS NULL"),
        ),
    )
