import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session as DbSession

from app.auth.models import User
from app.banks import service as banks_service
from app.core.envelope import Envelope
from app.core.errors import AppError
from app.core.plaid_client import ensure_plaid_enabled
from app.database import get_db
from app.dependencies import get_current_user
from app.jobs.models import Job
from app.jobs.service import create_job
from app.sync.schemas import JobStatus, SyncTriggerRequest, SyncTriggerResponse
from app.sync.tasks import sync_balances_task, sync_transactions_task

router = APIRouter(prefix="/sync", tags=["sync"])


@router.get("/jobs/{job_id}", response_model=Envelope[JobStatus])
def get_job(
    job_id: uuid.UUID, db: DbSession = Depends(get_db), user: User = Depends(get_current_user)
) -> dict[str, JobStatus]:
    job = db.get(Job, job_id)
    if job is None or job.owner_id != user.id:
        raise AppError(404, "not_found", "Job not found.")
    return {"data": JobStatus.from_job(job)}


@router.post(
    "/transactions",
    response_model=Envelope[SyncTriggerResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_transaction_sync(
    body: SyncTriggerRequest = SyncTriggerRequest(),
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, SyncTriggerResponse]:
    if body.bank_id is not None:
        banks_service.get_bank(db, user, body.bank_id)  # 404s before enqueueing anything
    ensure_plaid_enabled(db, user)
    job = create_job(db, "transaction_sync", owner_id=user.id)
    sync_transactions_task.delay(
        str(job.id), str(user.id), str(body.bank_id) if body.bank_id else None
    )
    return {"data": SyncTriggerResponse(job_id=job.id)}


@router.post(
    "/balances", response_model=Envelope[SyncTriggerResponse], status_code=status.HTTP_202_ACCEPTED
)
def trigger_balance_sync(
    body: SyncTriggerRequest = SyncTriggerRequest(),
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, SyncTriggerResponse]:
    if body.bank_id is not None:
        banks_service.get_bank(db, user, body.bank_id)  # 404s before enqueueing anything
    ensure_plaid_enabled(db, user)
    job = create_job(db, "balance_sync", owner_id=user.id)
    sync_balances_task.delay(str(job.id), str(user.id), str(body.bank_id) if body.bank_id else None)
    return {"data": SyncTriggerResponse(job_id=job.id)}
