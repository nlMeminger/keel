import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session as DbSession

from app.auth.models import User
from app.core.envelope import Envelope, paginate
from app.database import get_db
from app.dependencies import PaginationParams, get_current_user, pagination_params
from app.recurring_transactions import service
from app.recurring_transactions.schemas import (
    RecurringTransactionCreateRequest,
    RecurringTransactionPaymentCreateRequest,
    RecurringTransactionPublic,
    RecurringTransactionUpdateRequest,
)

router = APIRouter(prefix="/recurring-transactions", tags=["recurring-transactions"])


@router.get("")
def list_recurring(
    pagination: PaginationParams = Depends(pagination_params),
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    stmt = service.list_recurring_stmt(user)
    rows, meta = paginate(db, stmt, pagination.page, pagination.page_size)
    return {
        "data": [RecurringTransactionPublic.from_recurring(row) for row in rows],
        "pagination": meta.model_dump(),
    }


@router.post(
    "", response_model=Envelope[RecurringTransactionPublic], status_code=status.HTTP_201_CREATED
)
def create_recurring(
    body: RecurringTransactionCreateRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, RecurringTransactionPublic]:
    row = service.create_recurring(
        db,
        user,
        name=body.name,
        amount_expected=body.amount_expected,
        frequency=body.frequency,
        account_id=body.account_id,
        category_id=body.category_id,
        merchant_id=body.merchant_id,
        next_due_date=body.next_due_date,
        is_bill=body.is_bill,
    )
    return {"data": RecurringTransactionPublic.from_recurring(row)}


@router.patch("/{recurring_id}", response_model=Envelope[RecurringTransactionPublic])
def update_recurring(
    recurring_id: uuid.UUID,
    body: RecurringTransactionUpdateRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, RecurringTransactionPublic]:
    fields = body.model_dump(exclude_unset=True)
    row = service.update_recurring(db, user, recurring_id, fields)
    return {"data": RecurringTransactionPublic.from_recurring(row)}


@router.delete("/{recurring_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recurring(
    recurring_id: uuid.UUID, db: DbSession = Depends(get_db), user: User = Depends(get_current_user)
) -> None:
    service.delete_recurring(db, user, recurring_id)


@router.post(
    "/{recurring_id}/payments",
    response_model=Envelope[RecurringTransactionPublic],
    status_code=status.HTTP_201_CREATED,
)
def add_payment(
    recurring_id: uuid.UUID,
    body: RecurringTransactionPaymentCreateRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, RecurringTransactionPublic]:
    row = service.record_payment(db, user, recurring_id, amount=body.amount, payment_date=body.date)
    return {"data": RecurringTransactionPublic.from_recurring(row)}
