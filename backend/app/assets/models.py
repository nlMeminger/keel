import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Asset(Base):
    """A non-Plaid-linked net worth item — property, vehicles, etc. (API_SPEC.md §12).

    Every current_value change writes a Metrics row the same way a manual account's balance
    change does (4.9) — without that, /reports/net-worth-history would never include assets,
    since it reconstructs net worth purely from Metrics entries."""

    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str]
    # Free-form, same style as Metrics.type (e.g. "real_estate", "vehicle").
    asset_type: Mapped[str]
    current_value: Mapped[Decimal] = mapped_column(Numeric(14, 2))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
