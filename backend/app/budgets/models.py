import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Budget(Base):
    """category_id NULL = an overall budget across all non-transfer spending; set = scoped
    to one category (API_SPEC.md §9). `period` is 'monthly' only for v1 — no rollover, no
    custom windows. Spend-so-far is never stored here; it's always computed live from
    Transaction rows (see budgets/service.py)."""

    __tablename__ = "budgets"
    __table_args__ = (CheckConstraint("period IN ('monthly')", name="ck_budgets_period"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        index=True,
        default=None,
    )
    amount_limit: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    period: Mapped[str] = mapped_column(default="monthly", server_default="monthly")
    start_date: Mapped[date] = mapped_column(Date)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
