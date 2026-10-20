import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

ACCOUNT_TYPES = (
    "checking",
    "savings",
    "credit_card",
    "investment",
    "loan",
    "mortgage",
    "student_loan",
)


class Account(Base):
    """Polymorphic account: one table for every type, type-specific fields live in `detail`
    (API_SPEC.md §4) rather than sibling tables or SQLAlchemy inheritance."""

    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint(
            "account_type IN ('checking','savings','credit_card','investment',"
            "'loan','mortgage','student_loan')",
            name="ck_accounts_account_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str]
    account_type: Mapped[str]
    # Always non-negative regardless of asset vs. liability type — a credit card's balance is
    # "how much is owed," not a negated number. Net-worth math (Phase 6) subtracts liability
    # account_types rather than expecting a pre-negated sign here.
    balance: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")
    # Always False in Phase 4 — no code path sets it. Phase 7 flips it True at real Plaid-link
    # time; Holding's 403-on-Plaid-linked-account check (4.14) needs this flag to exist now.
    is_plaid_linked: Mapped[bool] = mapped_column(default=False, server_default="false")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
