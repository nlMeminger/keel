import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CategoryRule(Base):
    """A fixed, AND-ed set of optional conditions rather than a general condition DSL
    (SPEC.md §5) — `merchant_contains`, `amount_min`/`amount_max`, `account_id`. `priority`
    breaks ties when multiple rules match the same transaction: lower value wins, evaluated
    first in `/category-rules/apply` (app/category_rules/service.py)."""

    __tablename__ = "category_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), index=True, default=None
    )
    merchant_contains: Mapped[str | None] = mapped_column(default=None)
    amount_min: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), default=None)
    amount_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), default=None)
    priority: Mapped[int] = mapped_column(Integer, default=100, server_default="100")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
