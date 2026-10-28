import uuid

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime

from packages.db.models.base import Base


class File(Base):
    """Single storage provider (Cloudinary) — see .agents/decisions.md for why the
    `storage_provider` column and `interview_audio` file_type from doc/SRS/00 §5 were dropped
    in favor of doc/multi-agent-architecture/00 §4's corrected shape."""

    __tablename__ = "files"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    public_url: Mapped[str | None] = mapped_column(Text)
    file_type: Mapped[str | None] = mapped_column(Text)  # resume | certificate | ppt | photo
    uploaded_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Matches `fraud/router.py::_latest_photo_files` exactly — it IN-filters
    # owner_user_id, equality-filters file_type, and orders by
    # (owner_user_id, uploaded_at DESC) to pick each user's newest photo. Column order
    # here lets that query use the index for the filter *and* the sort; unindexed it was
    # a sequential scan of every file row plus an explicit sort, once per fraud check.
    __table_args__ = (
        Index("idx_files_owner_type_uploaded", "owner_user_id", "file_type", uploaded_at.desc()),
    )
