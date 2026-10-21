import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

TRANSFER_STATUSES = ("none", "suggested", "confirmed", "rejected")


class Transaction(Base):
    """A manually-entered or (Phase 7+) Plaid-synced ledger entry (API_SPEC.md §5).

    amount: positive = inflow/income, negative = outflow/expense. Plaid's own API uses the
    opposite convention — Phase 7's sync boundary will need an explicit sign-flip translation
    when Plaid-sourced transactions start writing into this same table.
    """

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint(
            "transfer_status IN ('none','suggested','confirmed','rejected')",
            name="ck_transactions_transfer_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Denormalized directly onto the row (not just reachable via account.user_id) so every
    # ownership-scoped list/filter query is a single-table WHERE.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), index=True
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

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    description: Mapped[str]
    notes: Mapped[str | None] = mapped_column(default=None)
    date: Mapped[date] = mapped_column(Date, index=True)
    pending: Mapped[bool] = mapped_column(default=False, server_default="false")
    # Plaid's own transaction_id — the stable key sync upserts against (added/modified/
    # removed from /transactions/sync all key off this). Null for manually-entered rows.
    plaid_transaction_id: Mapped[str | None] = mapped_column(unique=True, index=True, default=None)

    is_transfer: Mapped[bool] = mapped_column(default=False, server_default="false")
    paired_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="SET NULL"), default=None
    )
    transfer_status: Mapped[str] = mapped_column(default="none", server_default="none")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
