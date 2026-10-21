import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

RECURRING_FREQUENCIES = ("weekly", "monthly", "quarterly", "yearly")


class RecurringTransaction(Base):
    """A manually-entered bill/subscription (API_SPEC.md §11). Scheduled auto-detection is
    deferred post-v1 (ROADMAP.md Deferred section) — every row here is user-created for now."""

    __tablename__ = "recurring_transactions"
    __table_args__ = (
        CheckConstraint(
            "frequency IN ('weekly','monthly','quarterly','yearly')",
            name="ck_recurring_transactions_frequency",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="SET NULL"), index=True, default=None
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        index=True,
        default=None,
    )
    merchant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("merchants.id", ondelete="SET NULL"),
        index=True,
        default=None,
    )
    name: Mapped[str]
    amount_expected: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    frequency: Mapped[str]
    next_due_date: Mapped[date | None] = mapped_column(Date, default=None)
    # Set from the most recent RecurringTransactionPayment, not editable directly via PATCH.
    last_paid_date: Mapped[date | None] = mapped_column(Date, default=None)
    is_bill: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RecurringTransactionPayment(Base):
    """Nested under a RecurringTransaction — no own user_id, ownership is checked once via
    the parent (same pattern as GoalContribution under SavingsGoal)."""

    __tablename__ = "recurring_transaction_payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recurring_transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recurring_transactions.id", ondelete="CASCADE"),
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    date: Mapped[date] = mapped_column(Date)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
