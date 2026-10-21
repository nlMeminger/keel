import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.auth.models import User
from app.banks import service
from app.banks.models import Bank, PlaidItem
from app.banks.schemas import BankPublic, BankSyncResponse
from app.core.envelope import Envelope, paginate
from app.core.plaid_client import ensure_plaid_enabled
from app.database import get_db
from app.dependencies import PaginationParams, get_current_user, pagination_params
from app.jobs.service import create_job
from app.sync.tasks import full_bank_sync_task

router = APIRouter(prefix="/banks", tags=["banks"])


@router.get("")
def list_banks(
    pagination: PaginationParams = Depends(pagination_params),
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    stmt = select(Bank).where(Bank.owner_id == user.id).order_by(Bank.created_at)
    rows, meta = paginate(db, stmt, pagination.page, pagination.page_size)
    data = []
    for bank in rows:
        item = db.get(PlaidItem, bank.plaid_item_id)
        assert item is not None
        account_count = service.count_active_accounts(db, bank.id)
        data.append(BankPublic.from_bank(bank, item, account_count))
    return {"data": data, "pagination": meta.model_dump()}


@router.get("/{bank_id}", response_model=Envelope[BankPublic])
def get_bank(
    bank_id: uuid.UUID, db: DbSession = Depends(get_db), user: User = Depends(get_current_user)
) -> dict[str, BankPublic]:
    bank, item = service.get_bank_with_item(db, user, bank_id)
    account_count = service.count_active_accounts(db, bank.id)
    return {"data": BankPublic.from_bank(bank, item, account_count)}


@router.post(
    "/{bank_id}/sync",
    response_model=Envelope[BankSyncResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
def sync_bank(
    bank_id: uuid.UUID, db: DbSession = Depends(get_db), user: User = Depends(get_current_user)
) -> dict[str, BankSyncResponse]:
    service.get_bank(db, user, bank_id)  # 404s before enqueueing anything for another user's id
    ensure_plaid_enabled(user)  # likewise: 403 here, not a 500 surfaced from inside the task
    job = create_job(db, "transaction_sync", owner_id=user.id)
    full_bank_sync_task.delay(str(job.id), str(user.id), str(bank_id))
    return {"data": BankSyncResponse(job_id=job.id)}


@router.delete("/{bank_id}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_bank(
    bank_id: uuid.UUID, db: DbSession = Depends(get_db), user: User = Depends(get_current_user)
) -> None:
    service.unlink_bank(db, user, bank_id)
