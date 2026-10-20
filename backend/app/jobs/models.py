import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

JOB_TYPES = (
    "transaction_sync",
    "balance_sync",
    "bulk_import",
    "category_rule_apply",
    "plaid_item_reconciliation",
)
JOB_STATUSES = ("pending", "running", "succeeded", "failed")


class Job(Base):
    """Status record for any write whose latency isn't bounded (API_SPEC.md §16)."""

    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "type IN ('transaction_sync','balance_sync','bulk_import',"
            "'category_rule_apply','plaid_item_reconciliation')",
            name="ck_jobs_type",
        ),
        CheckConstraint(
            "status IN ('pending','running','succeeded','failed')", name="ck_jobs_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type: Mapped[str]
    status: Mapped[str] = mapped_column(default="pending", server_default="pending")
    # Nullable: some jobs (e.g. an admin-triggered sync-all) aren't scoped to one user.
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, default=None
    )

    progress_current: Mapped[int | None] = mapped_column(default=None)
    progress_total: Mapped[int | None] = mapped_column(default=None)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    error: Mapped[str | None] = mapped_column(default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
