import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session as DbSession

from app.auth.models import User
from app.core.envelope import Envelope, paginate
from app.database import get_db
from app.dependencies import PaginationParams, get_current_user, pagination_params
from app.merchants import service
from app.merchants.schemas import MerchantCreateRequest, MerchantPublic, MerchantUpdateRequest

router = APIRouter(prefix="/merchants", tags=["merchants"])


@router.get("")
def list_merchants(
    pagination: PaginationParams = Depends(pagination_params),
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    stmt = service.list_merchants_stmt(user)
    rows, meta = paginate(db, stmt, pagination.page, pagination.page_size)
    return {
        "data": [MerchantPublic.model_validate(row) for row in rows],
        "pagination": meta.model_dump(),
    }


@router.post("", response_model=Envelope[MerchantPublic], status_code=status.HTTP_201_CREATED)
def create_merchant(
    body: MerchantCreateRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, MerchantPublic]:
    merchant = service.create_merchant(db, user, name=body.name, aliases=body.aliases)
    return {"data": MerchantPublic.model_validate(merchant)}


@router.patch("/{merchant_id}", response_model=Envelope[MerchantPublic])
def update_merchant(
    merchant_id: uuid.UUID,
    body: MerchantUpdateRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, MerchantPublic]:
    merchant = service.update_merchant(
        db, user, merchant_id, name=body.name, aliases=body.aliases
    )
    return {"data": MerchantPublic.model_validate(merchant)}


@router.delete("/{merchant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_merchant(
    merchant_id: uuid.UUID, db: DbSession = Depends(get_db), user: User = Depends(get_current_user)
) -> None:
    service.delete_merchant(db, user, merchant_id)
