import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

BANK_HEALTH_STATUSES = ("healthy", "needs_reauth", "error")


class PlaidItem(Base):
    """One Plaid Item per bank connection (SPEC.md §5). `access_token` is encrypted at rest
    (app.core.encryption) — reversible, since the app must decrypt and reuse it on every
    Plaid call, unlike Session/ApiToken's one-way-hashed secrets."""

    __tablename__ = "plaid_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    access_token: Mapped[str]
    item_id: Mapped[str] = mapped_column(unique=True, index=True)
    institution_id: Mapped[str]
    institution_name: Mapped[str]
    # Unset until the first /transactions/sync call for this item; passed back on every
    # later call so only what changed since is returned.
    cursor: Mapped[str | None] = mapped_column(default=None)
    # Set on unlink (DELETE /banks/{id}, or an admin hard-deleting a user) — row retained
    # rather than dropped so the ghost-item check (7.11) has something to verify against.
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


PLAID_CALL_STATUSES = ("success", "error")


class PlaidAPICall(Base):
    """One row per real Plaid API call made on a user's behalf (API_SPEC.md §18) — what
    /admin/plaid/api-stats aggregates and /admin/plaid/calls lists raw, and what
    monthly_call_limit enforcement counts live against. Never written for a sandbox-only
    simulation call a test makes to set up fixture state (e.g. sandbox/public_token/create)
    — those don't represent anything the app itself calls in production."""

    __tablename__ = "plaid_api_calls"
    __table_args__ = (
        CheckConstraint("status IN ('success','error')", name="ck_plaid_api_calls_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    endpoint: Mapped[str] = mapped_column(index=True)
    status: Mapped[str]
    error_code: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class Bank(Base):
    """A user's linked bank connection, one-to-one with a PlaidItem (API_SPEC.md §3)."""

    __tablename__ = "banks"
    __table_args__ = (
        CheckConstraint("health IN ('healthy','needs_reauth','error')", name="ck_banks_health"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    plaid_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plaid_items.id", ondelete="CASCADE"), unique=True
    )
    # Set from Plaid's own signals (a webhook or an API error like ITEM_LOGIN_REQUIRED),
    # never user-editable directly.
    health: Mapped[str] = mapped_column(default="healthy", server_default="healthy")
    # Unset until the first sync completes — a Bank can briefly have zero accounts (Link
    # succeeded, first account pull hasn't run yet) without that being an error state.
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Institution(Base):
    """Institution reference list (API_SPEC.md §18's `POST /admin/banks/seed`) — pulled
    from Plaid's `/institutions/get`, idempotent on `plaid_institution_id`. Unused by Plaid
    Link itself today (Link's own hosted widget already handles institution search), kept
    for a future "pick your bank" screen that doesn't need to round-trip to Plaid for it."""

    __tablename__ = "institutions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plaid_institution_id: Mapped[str] = mapped_column(unique=True, index=True)
    name: Mapped[str]
    logo_url: Mapped[str | None] = mapped_column(default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
