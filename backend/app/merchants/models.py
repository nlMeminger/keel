import uuid
from datetime import datetime

from sqlalchemy import ARRAY, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Merchant(Base):
    """Pure aliasing/grouping construct for display and search (API_SPEC.md §8) — merchant-
    based auto-categorization goes through CategoryRule (Phase 5), not a field here."""

    __tablename__ = "merchants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str]
    # Raw bank-provided description strings that map to this merchant. A flat string list fits
    # ARRAY better than JSONB (the convention used for nested/structured columns elsewhere).
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, server_default="{}")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
