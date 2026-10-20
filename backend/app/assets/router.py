import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session as DbSession

from app.assets import service
from app.assets.schemas import AssetCreateRequest, AssetPublic, AssetUpdateRequest
from app.auth.models import User
from app.core.envelope import Envelope, paginate
from app.database import get_db
from app.dependencies import PaginationParams, get_current_user, pagination_params

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("")
def list_assets(
    pagination: PaginationParams = Depends(pagination_params),
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    stmt = service.list_assets_stmt(user)
    rows, meta = paginate(db, stmt, pagination.page, pagination.page_size)
    return {
        "data": [AssetPublic.model_validate(row) for row in rows],
        "pagination": meta.model_dump(),
    }


@router.post("", response_model=Envelope[AssetPublic], status_code=status.HTTP_201_CREATED)
def create_asset(
    body: AssetCreateRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, AssetPublic]:
    asset = service.create_asset(
        db, user, name=body.name, asset_type=body.asset_type, current_value=body.current_value
    )
    return {"data": AssetPublic.model_validate(asset)}


@router.patch("/{asset_id}", response_model=Envelope[AssetPublic])
def update_asset(
    asset_id: uuid.UUID,
    body: AssetUpdateRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, AssetPublic]:
    asset = service.update_asset(
        db,
        user,
        asset_id,
        name=body.name,
        asset_type=body.asset_type,
        current_value=body.current_value,
    )
    return {"data": AssetPublic.model_validate(asset)}


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(
    asset_id: uuid.UUID, db: DbSession = Depends(get_db), user: User = Depends(get_current_user)
) -> None:
    service.delete_asset(db, user, asset_id)
