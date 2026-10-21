import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DbSession

from app.admin import service
from app.admin.dependencies import require_admin
from app.admin.schemas import AdminAuditLogPublic
from app.auth.models import User
from app.core.envelope import Page, paginate
from app.database import get_db
from app.dependencies import PaginationParams, pagination_params

router = APIRouter(prefix="/admin/audit-log", tags=["admin"])


@router.get("", response_model=Page[AdminAuditLogPublic])
def list_audit_log(
    admin_user_id: uuid.UUID | None = Query(default=None),
    action: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    pagination: PaginationParams = Depends(pagination_params),
    db: DbSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> dict[str, object]:
    stmt = service.list_audit_log_stmt(admin_user_id, action, date_from, date_to)
    rows, meta = paginate(db, stmt, pagination.page, pagination.page_size)
    return {
        "data": [AdminAuditLogPublic.from_log(row) for row in rows],
        "pagination": meta.model_dump(),
    }
