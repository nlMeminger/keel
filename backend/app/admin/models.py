import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LogEntry(Base):
    """Backs `GET /admin/logs` (API_SPEC.md §18). Persisted via a logging.Handler
    (app.admin.log_capture) attached to the "app" logger hierarchy — paginating/filtering a
    DB table is simpler and container-count-independent compared to tailing a file/stdout
    stream. `message` is masked (app.admin.log_capture.mask_secrets) before it's ever
    written here, not just at read time."""

    __tablename__ = "log_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    level: Mapped[str] = mapped_column(index=True)
    logger_name: Mapped[str] = mapped_column(index=True)
    message: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class ApiToken(Base):
    """External API access (API_SPEC.md §18) — issued by an admin, authenticates as the
    bound `user_id` via `Authorization: Bearer <token>` same as a user's own JWT
    (app.dependencies.get_current_user tries JWT decode first, then falls back to this
    table). `token_hash` is one-way hashed like Session.token_hash (app.core.security.
    hash_token) — the raw secret is shown exactly once, at creation, never stored."""

    __tablename__ = "api_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    label: Mapped[str]
    # ["read"] or ["read","write"] (API_SPEC.md §18) — validated at the Pydantic layer
    # (app.admin.schemas), same free-form-at-the-DB-layer tradeoff as Metrics.type.
    scopes: Mapped[list[str]] = mapped_column(JSONB)
    token_hash: Mapped[str] = mapped_column(unique=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
