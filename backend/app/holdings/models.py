import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Holding(Base):
    """A position within an investment Account (API_SPEC.md §4) — nested under
    /accounts/{account_id}/holdings, no own user_id since ownership is checked once via the
    parent account. Plaid-sourced holdings (source='plaid') are read-only, populated by sync
    in Phase 7; every Phase 4 holding is source='manual'."""

    __tablename__ = "holdings"
    __table_args__ = (CheckConstraint("source IN ('plaid','manual')", name="ck_holdings_source"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    # Unset for a manually-entered holding with no Plaid security match.
    security_id: Mapped[str | None] = mapped_column(default=None)
    symbol: Mapped[str]
    name: Mapped[str]
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    cost_basis: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    # Nullable — manual holdings don't get a live value the way Plaid-synced ones do; stays
    # null until the user optionally fills it in.
    current_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), default=None)
    source: Mapped[str] = mapped_column(default="manual", server_default="manual")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
