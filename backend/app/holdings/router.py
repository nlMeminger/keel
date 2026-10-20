import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session as DbSession

from app.auth.models import User
from app.core.envelope import Envelope, paginate
from app.database import get_db
from app.dependencies import PaginationParams, get_current_user, pagination_params
from app.holdings import service
from app.holdings.schemas import HoldingCreateRequest, HoldingPublic, HoldingUpdateRequest

router = APIRouter(prefix="/accounts/{account_id}/holdings", tags=["holdings"])


@router.get("")
def list_holdings(
    account_id: uuid.UUID,
    pagination: PaginationParams = Depends(pagination_params),
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    stmt = service.list_holdings_stmt(db, user, account_id)
    rows, meta = paginate(db, stmt, pagination.page, pagination.page_size)
    return {
        "data": [HoldingPublic.model_validate(row) for row in rows],
        "pagination": meta.model_dump(),
    }


@router.post("", response_model=Envelope[HoldingPublic], status_code=status.HTTP_201_CREATED)
def create_holding(
    account_id: uuid.UUID,
    body: HoldingCreateRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, HoldingPublic]:
    holding = service.create_holding(
        db,
        user,
        account_id,
        symbol=body.symbol,
        name=body.name,
        quantity=body.quantity,
        cost_basis=body.cost_basis,
    )
    return {"data": HoldingPublic.model_validate(holding)}


@router.patch("/{holding_id}", response_model=Envelope[HoldingPublic])
def update_holding(
    account_id: uuid.UUID,
    holding_id: uuid.UUID,
    body: HoldingUpdateRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, HoldingPublic]:
    holding = service.update_holding(
        db,
        user,
        account_id,
        holding_id,
        symbol=body.symbol,
        name=body.name,
        quantity=body.quantity,
        cost_basis=body.cost_basis,
        current_value=body.current_value,
    )
    return {"data": HoldingPublic.model_validate(holding)}


@router.delete("/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_holding(
    account_id: uuid.UUID,
    holding_id: uuid.UUID,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    service.delete_holding(db, user, account_id, holding_id)
