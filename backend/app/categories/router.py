import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session as DbSession

from app.auth.models import User
from app.categories import service
from app.categories.schemas import CategoryCreateRequest, CategoryPublic, CategoryUpdateRequest
from app.core.envelope import Envelope, paginate
from app.database import get_db
from app.dependencies import PaginationParams, get_current_user, pagination_params

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("")
def list_categories(
    scope: Literal["system", "custom", "all"] = Query(default="all"),
    pagination: PaginationParams = Depends(pagination_params),
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    stmt = service.list_categories_stmt(user, scope)
    rows, meta = paginate(db, stmt, pagination.page, pagination.page_size)
    return {
        "data": [CategoryPublic.model_validate(row) for row in rows],
        "pagination": meta.model_dump(),
    }


@router.post("", response_model=Envelope[CategoryPublic], status_code=status.HTTP_201_CREATED)
def create_category(
    body: CategoryCreateRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, CategoryPublic]:
    category = service.create_category(
        db,
        user,
        primary_category=body.primary_category,
        detailed_category=body.detailed_category,
        icon=body.icon,
        color=body.color,
    )
    return {"data": CategoryPublic.model_validate(category)}


@router.patch("/{category_id}", response_model=Envelope[CategoryPublic])
def update_category(
    category_id: uuid.UUID,
    body: CategoryUpdateRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, CategoryPublic]:
    category = service.update_category(
        db,
        user,
        category_id,
        primary_category=body.primary_category,
        detailed_category=body.detailed_category,
        icon=body.icon,
        color=body.color,
    )
    return {"data": CategoryPublic.model_validate(category)}


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: uuid.UUID,
    reassign_to: uuid.UUID | None = Query(default=None),
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    service.delete_category(db, user, category_id, reassign_to)
