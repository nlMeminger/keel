import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session as DbSession

from app.accounts import service
from app.accounts.schemas import AccountCreateRequest, AccountPublic, AccountUpdateRequest
from app.auth.models import User
from app.core.envelope import Envelope, paginate, single_page
from app.database import get_db
from app.dependencies import PaginationParams, get_current_user, pagination_params
from app.metrics import service as metrics_service
from app.metrics.schemas import MetricPublic

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("")
def list_accounts(
    active: bool | None = Query(default=None),
    pagination: PaginationParams = Depends(pagination_params),
    account_type: str | None = Query(default=None, alias="type"),
    bank_id: uuid.UUID | None = Query(default=None),
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    stmt = service.list_accounts_stmt(
        user, account_type=account_type, active=active, bank_id=bank_id
    )
    rows, meta = paginate(db, stmt, pagination.page, pagination.page_size)
    return {
        "data": [AccountPublic.model_validate(row) for row in rows],
        "pagination": meta.model_dump(),
    }


@router.get("/{account_id}", response_model=Envelope[AccountPublic])
def get_account(
    account_id: uuid.UUID, db: DbSession = Depends(get_db), user: User = Depends(get_current_user)
) -> dict[str, AccountPublic]:
    account = service.get_account(db, user, account_id)
    return {"data": AccountPublic.model_validate(account)}


@router.post("", response_model=Envelope[AccountPublic], status_code=status.HTTP_201_CREATED)
def create_account(
    body: AccountCreateRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, AccountPublic]:
    account = service.create_account(
        db,
        user,
        name=body.name,
        account_type=body.account_type,
        balance=body.balance,
        detail=body.detail,
    )
    return {"data": AccountPublic.model_validate(account)}


@router.patch("/{account_id}", response_model=Envelope[AccountPublic])
def update_account(
    account_id: uuid.UUID,
    body: AccountUpdateRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, AccountPublic]:
    account = service.update_account(
        db,
        user,
        account_id,
        name=body.name,
        account_type=body.account_type,
        balance=body.balance,
        detail=body.detail,
    )
    return {"data": AccountPublic.model_validate(account)}


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_account(
    account_id: uuid.UUID, db: DbSession = Depends(get_db), user: User = Depends(get_current_user)
) -> None:
    service.deactivate_account(db, user, account_id)


@router.get("/{account_id}/balance-history")
def account_balance_history(
    account_id: uuid.UUID,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    """Convenience read over `/metrics?type=account_balance&account_id=...` for charting one
    account (API_SPEC.md §15) — same ownership check as every other /accounts/{id} route."""
    service.get_account(db, user, account_id)
    stmt = metrics_service.list_metrics_stmt(
        user,
        metric_type="account_balance",
        account_id=account_id,
        asset_id=None,
        date_from=date_from,
        date_to=date_to,
    )
    rows = db.scalars(stmt).all()
    return single_page([MetricPublic.model_validate(row) for row in rows])
