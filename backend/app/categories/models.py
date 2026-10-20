import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

#: Seeded, never created directly through the API — only assigned automatically when a
#: transfer pairing is confirmed (4.13).
TRANSFER_CATEGORY_NAME = "Transfer"


class Category(Base):
    """A system category (owner_id NULL, read-only) or a user's custom one (API_SPEC.md §6)."""

    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Nullable + named owner_id (not user_id) to mirror Job.owner_id: NULL means "system",
    # not "unowned" — the only other nullable-ownership precedent in the codebase.
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, default=None
    )
    primary_category: Mapped[str]
    detailed_category: Mapped[str | None] = mapped_column(default=None)
    icon: Mapped[str | None] = mapped_column(default=None)
    color: Mapped[str | None] = mapped_column(default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
