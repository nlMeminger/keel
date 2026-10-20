import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session as DbSession

from app.auth.models import User
from app.core.envelope import Envelope, paginate
from app.database import get_db
from app.dependencies import PaginationParams, get_current_user, pagination_params
from app.transactions import service
from app.transactions.schemas import (
    SortOption,
    TransactionCreateRequest,
    TransactionPublic,
    TransactionUpdateRequest,
    TransferStatus,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("")
def list_transactions(
    account_id: uuid.UUID | None = Query(default=None),
    category_id: uuid.UUID | None = Query(default=None),
    merchant: str | None = Query(default=None),
    description: str | None = Query(default=None),
    amount_min: Decimal | None = Query(default=None),
    amount_max: Decimal | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    pending: bool | None = Query(default=None),
    transfer_status: TransferStatus | None = Query(default=None),
    sort: SortOption = Query(default="date_desc"),
    pagination: PaginationParams = Depends(pagination_params),
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    stmt = service.list_transactions_stmt(
        user,
        account_id=account_id,
        category_id=category_id,
        merchant=merchant,
        description=description,
        amount_min=amount_min,
        amount_max=amount_max,
        date_from=date_from,
        date_to=date_to,
        pending=pending,
        transfer_status=transfer_status,
        sort=sort,
    )
    rows, meta = paginate(db, stmt, pagination.page, pagination.page_size)
    return {
        "data": [TransactionPublic.model_validate(row) for row in rows],
        "pagination": meta.model_dump(),
    }


@router.get("/{transaction_id}", response_model=Envelope[TransactionPublic])
def get_transaction(
    transaction_id: uuid.UUID,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, TransactionPublic]:
    txn = service.get_transaction(db, user, transaction_id)
    return {"data": TransactionPublic.model_validate(txn)}


@router.post("", response_model=Envelope[TransactionPublic], status_code=status.HTTP_201_CREATED)
def create_transaction(
    body: TransactionCreateRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, TransactionPublic]:
    txn = service.create_transaction(
        db,
        user,
        account_id=body.account_id,
        category_id=body.category_id,
        merchant_id=body.merchant_id,
        amount=body.amount,
        description=body.description,
        notes=body.notes,
        txn_date=body.date,
        pending=body.pending,
    )
    return {"data": TransactionPublic.model_validate(txn)}


@router.patch("/{transaction_id}", response_model=Envelope[TransactionPublic])
def update_transaction(
    transaction_id: uuid.UUID,
    body: TransactionUpdateRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, TransactionPublic]:
    fields = body.model_dump(exclude_unset=True)
    txn = service.update_transaction(db, user, transaction_id, fields)
    return {"data": TransactionPublic.model_validate(txn)}


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: uuid.UUID,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    service.delete_transaction(db, user, transaction_id)
