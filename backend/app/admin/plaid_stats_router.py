import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DbSession

from app.admin import service
from app.admin.dependencies import require_admin
from app.admin.schemas import PlaidApiCallPublic, PlaidStatsGroupBy
from app.auth.models import User
from app.core.envelope import paginate, single_page
from app.database import get_db
from app.dependencies import PaginationParams, pagination_params

router = APIRouter(prefix="/admin/plaid", tags=["admin"])


@router.get("/api-stats")
def api_stats(
    group_by: PlaidStatsGroupBy = Query(...),
    user_id: uuid.UUID | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    db: DbSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> dict[str, object]:
    rows = service.plaid_api_stats(db, group_by, user_id, date_from, date_to)
    return single_page(rows)


@router.get("/calls")
def list_calls(
    user_id: uuid.UUID | None = Query(default=None),
    endpoint: str | None = Query(default=None),
    status: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    pagination: PaginationParams = Depends(pagination_params),
    db: DbSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> dict[str, object]:
    stmt = service.list_plaid_calls_stmt(user_id, endpoint, status, date_from, date_to)
    rows, meta = paginate(db, stmt, pagination.page, pagination.page_size)
    return {
        "data": [PlaidApiCallPublic.model_validate(row) for row in rows],
        "pagination": meta.model_dump(),
    }
