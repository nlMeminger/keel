import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Notification(Base):
    """Server-created only — no client POST (API_SPEC.md §13). `type` is free-form, same
    style as `Metrics.type`/`Asset.asset_type`. `related_type`/`related_id` point back at
    whatever triggered it (e.g. a Budget or SavingsGoal) without a hard FK, since the related
    row's table varies by notification type."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str]
    title: Mapped[str]
    body: Mapped[str]
    related_type: Mapped[str | None] = mapped_column(default=None)
    related_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), default=None)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
