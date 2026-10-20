import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session as DbSession

from app.accounts import service
from app.accounts.schemas import AccountCreateRequest, AccountPublic, AccountUpdateRequest
from app.auth.models import User
from app.core.envelope import Envelope, paginate
from app.database import get_db
from app.dependencies import PaginationParams, get_current_user, pagination_params

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("")
def list_accounts(
    active: bool | None = Query(default=None),
    pagination: PaginationParams = Depends(pagination_params),
    account_type: str | None = Query(default=None, alias="type"),
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    stmt = service.list_accounts_stmt(user, account_type=account_type, active=active)
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
