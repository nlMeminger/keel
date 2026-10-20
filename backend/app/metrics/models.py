import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Metric(Base):
    """A point-in-time value (API_SPEC.md §14) — e.g. a credit_score reading, or (usually
    written implicitly, see 4.9) an account_balance/asset_value snapshot. Append-only: a
    repeated value change writes a new row rather than overwriting the last one, so every
    account and asset ends up with a real value history.

    account_id/asset_id are mutually exclusive (enforced by a CHECK constraint) — both-null
    is valid, for standalone metrics like credit_score that aren't tied to either."""

    __tablename__ = "metrics"
    __table_args__ = (
        CheckConstraint(
            "NOT (account_id IS NOT NULL AND asset_id IS NOT NULL)",
            name="ck_metrics_account_asset_exclusive",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Free-form key, e.g. "account_balance", "asset_value", "credit_score", or custom.
    type: Mapped[str] = mapped_column(index=True)
    value: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    date: Mapped[date] = mapped_column(Date, index=True)
    note: Mapped[str | None] = mapped_column(default=None)
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), index=True, default=None
    )
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), index=True, default=None
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
