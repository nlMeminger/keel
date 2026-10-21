import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session as DbSession

from app.admin import service
from app.admin.dependencies import require_admin
from app.admin.schemas import (
    AdminApiTokenCreateRequest,
    AdminApiTokenCreateResponseData,
    AdminApiTokenPublic,
    AdminApiTokenUpdateRequest,
)
from app.auth.models import User
from app.core.envelope import Envelope, paginate
from app.database import get_db
from app.dependencies import PaginationParams, pagination_params

router = APIRouter(prefix="/admin/api-tokens", tags=["admin"])


@router.get("")
def list_api_tokens(
    pagination: PaginationParams = Depends(pagination_params),
    db: DbSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> dict[str, object]:
    stmt = service.list_api_tokens_stmt()
    rows, meta = paginate(db, stmt, pagination.page, pagination.page_size)
    return {
        "data": [AdminApiTokenPublic.model_validate(row) for row in rows],
        "pagination": meta.model_dump(),
    }


@router.post(
    "",
    response_model=Envelope[AdminApiTokenCreateResponseData],
    status_code=status.HTTP_201_CREATED,
)
def create_api_token(
    body: AdminApiTokenCreateRequest,
    db: DbSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict[str, AdminApiTokenCreateResponseData]:
    token, secret = service.create_api_token(
        db, admin, body.user_id, body.label, list(body.scopes), body.expires_at
    )
    return {
        "data": AdminApiTokenCreateResponseData(
            token=AdminApiTokenPublic.model_validate(token), secret=secret
        )
    }


@router.patch("/{token_id}", response_model=Envelope[AdminApiTokenPublic])
def update_api_token(
    token_id: uuid.UUID,
    body: AdminApiTokenUpdateRequest,
    db: DbSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> dict[str, AdminApiTokenPublic]:
    token = service.get_api_token(db, token_id)
    updated = service.update_api_token(db, token, body.label, body.expires_at)
    return {"data": AdminApiTokenPublic.model_validate(updated)}


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_token(
    token_id: uuid.UUID, db: DbSession = Depends(get_db), _admin: User = Depends(require_admin)
) -> None:
    token = service.get_api_token(db, token_id)
    service.revoke_api_token(db, token)
