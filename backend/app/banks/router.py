import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.auth.models import User
from app.banks import service
from app.banks.models import Bank, PlaidItem
from app.banks.schemas import BankPublic
from app.core.envelope import Envelope, paginate
from app.database import get_db
from app.dependencies import PaginationParams, get_current_user, pagination_params

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
