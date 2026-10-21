import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
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
