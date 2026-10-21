import uuid
from typing import Any

from sqlalchemy.orm import Session as DbSession

from app.admin.models import AdminAuditLog
from app.auth.models import User


def record_audit_log(
    db: DbSession,
    admin: User,
    action: str,
    target_type: str,
    target_id: uuid.UUID | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Write-hook called by every admin write route (API_SPEC.md §18) right after its own
    service call succeeds. Never pass a secret (a token's raw value, a reset password) in
    `metadata` — this table is itself readable via GET /admin/audit-log."""
    db.add(
        AdminAuditLog(
            admin_user_id=admin.id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata_=metadata or {},
        )
    )
    db.commit()
