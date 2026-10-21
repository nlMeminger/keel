import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session as DbSession

from app.admin import service
from app.admin.audit import record_audit_log
from app.admin.dependencies import require_admin
from app.admin.schemas import (
    AdminConfigResponseData,
    AdminJobPublic,
    BankHealthCheckResponseData,
    LogEntryPublic,
    SyncAllTriggerResponseData,
)
from app.auth.models import User
from app.core.envelope import Envelope, paginate
from app.database import get_db
from app.dependencies import PaginationParams, pagination_params

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/jobs")
def list_jobs(
    job_type: str | None = Query(default=None, alias="type"),
    status_filter: str | None = Query(default=None, alias="status"),
    pagination: PaginationParams = Depends(pagination_params),
    db: DbSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> dict[str, object]:
    stmt = service.list_jobs_stmt(job_type, status_filter)
    rows, meta = paginate(db, stmt, pagination.page, pagination.page_size)
    return {
        "data": [AdminJobPublic.from_job(row) for row in rows],
        "pagination": meta.model_dump(),
    }


@router.get("/logs")
def list_logs(
    level: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    pagination: PaginationParams = Depends(pagination_params),
    db: DbSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> dict[str, object]:
    stmt = service.list_logs_stmt(level, date_from, date_to)
    rows, meta = paginate(db, stmt, pagination.page, pagination.page_size)
    return {
        "data": [LogEntryPublic.model_validate(row) for row in rows],
        "pagination": meta.model_dump(),
    }


@router.post(
    "/sync/transactions",
    response_model=Envelope[SyncAllTriggerResponseData],
    status_code=status.HTTP_202_ACCEPTED,
)
def sync_all_transactions(
    db: DbSession = Depends(get_db), admin: User = Depends(require_admin)
) -> dict[str, SyncAllTriggerResponseData]:
    job = service.trigger_sync_all_transactions(db)
    record_audit_log(
        db, admin, "sync.trigger_all_transactions", "system", None, {"job_id": str(job.id)}
    )
    return {"data": SyncAllTriggerResponseData(job_id=job.id)}


@router.post(
    "/sync/balances",
    response_model=Envelope[SyncAllTriggerResponseData],
    status_code=status.HTTP_202_ACCEPTED,
)
def sync_all_balances(
    db: DbSession = Depends(get_db), admin: User = Depends(require_admin)
) -> dict[str, SyncAllTriggerResponseData]:
    job = service.trigger_sync_all_balances(db)
    record_audit_log(
        db, admin, "sync.trigger_all_balances", "system", None, {"job_id": str(job.id)}
    )
    return {"data": SyncAllTriggerResponseData(job_id=job.id)}


@router.post("/banks/{bank_id}/health-check", response_model=Envelope[BankHealthCheckResponseData])
def health_check_bank(
    bank_id: uuid.UUID, db: DbSession = Depends(get_db), admin: User = Depends(require_admin)
) -> dict[str, BankHealthCheckResponseData]:
    checked_bank_id, health = service.check_bank_health(db, bank_id)
    record_audit_log(db, admin, "bank.health_check", "bank", checked_bank_id, {"health": health})
    return {"data": BankHealthCheckResponseData(bank_id=checked_bank_id, health=health)}


@router.post(
    "/plaid/reconcile-items",
    response_model=Envelope[SyncAllTriggerResponseData],
    status_code=status.HTTP_202_ACCEPTED,
)
def reconcile_plaid_items(
    db: DbSession = Depends(get_db), admin: User = Depends(require_admin)
) -> dict[str, SyncAllTriggerResponseData]:
    job = service.trigger_reconcile_items(db)
    record_audit_log(db, admin, "plaid.reconcile_items", "system", None, {"job_id": str(job.id)})
    return {"data": SyncAllTriggerResponseData(job_id=job.id)}


@router.get("/config", response_model=Envelope[AdminConfigResponseData])
def get_config(_admin: User = Depends(require_admin)) -> dict[str, AdminConfigResponseData]:
    return {"data": service.get_config()}
