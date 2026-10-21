import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session as DbSession

from app.admin import service
from app.admin.audit import record_audit_log
from app.admin.dependencies import require_admin
from app.admin.schemas import (
    AdminPlaidAccessUpdateRequest,
    AdminResetPasswordRequest,
    AdminResetPasswordResponseData,
    AdminUserCreateRequest,
    AdminUserCreateResponseData,
    AdminUserDeleteRequest,
    AdminUserPublic,
    AdminUserUpdateRequest,
)
from app.auth.models import User
from app.core.envelope import Envelope, Page, paginate
from app.database import get_db
from app.dependencies import PaginationParams, pagination_params

router = APIRouter(prefix="/admin/users", tags=["admin"])


@router.get("", response_model=Page[AdminUserPublic])
def list_users(
    role: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    pagination: PaginationParams = Depends(pagination_params),
    db: DbSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> dict[str, object]:
    stmt = service.list_users_stmt(role, status_filter)
    rows, meta = paginate(db, stmt, pagination.page, pagination.page_size)
    return {
        "data": [service.to_public(db, row) for row in rows],
        "pagination": meta.model_dump(),
    }


@router.post(
    "", response_model=Envelope[AdminUserCreateResponseData], status_code=status.HTTP_201_CREATED
)
def create_user(
    body: AdminUserCreateRequest,
    db: DbSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict[str, AdminUserCreateResponseData]:
    user, initial_password = service.create_user(
        db, email=body.email, name=body.name, role=body.role, password=body.password
    )
    record_audit_log(
        db, admin, "user.create", "user", user.id, {"email": body.email, "role": body.role}
    )
    return {
        "data": AdminUserCreateResponseData(
            user=service.to_public(db, user), initial_password=initial_password
        )
    }


@router.get("/{user_id}", response_model=Envelope[AdminUserPublic])
def get_user(
    user_id: uuid.UUID, db: DbSession = Depends(get_db), _admin: User = Depends(require_admin)
) -> dict[str, AdminUserPublic]:
    user = service.get_user(db, user_id)
    return {"data": service.to_public(db, user)}


@router.patch("/{user_id}", response_model=Envelope[AdminUserPublic])
def update_user(
    user_id: uuid.UUID,
    body: AdminUserUpdateRequest,
    db: DbSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict[str, AdminUserPublic]:
    user = service.get_user(db, user_id)
    updated = service.update_user(
        db,
        user,
        name=body.name,
        email=body.email,
        timezone=body.timezone,
        role=body.role,
        status=body.status,
    )
    record_audit_log(db, admin, "user.update", "user", user_id, body.model_dump(exclude_none=True))
    return {"data": service.to_public(db, updated)}


@router.post("/{user_id}/reset-password", response_model=Envelope[AdminResetPasswordResponseData])
def reset_password(
    user_id: uuid.UUID,
    body: AdminResetPasswordRequest,
    db: DbSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict[str, AdminResetPasswordResponseData]:
    user = service.get_user(db, user_id)
    temporary_password = service.reset_password(db, user, body.password)
    record_audit_log(db, admin, "user.reset_password", "user", user_id)  # never log a password
    return {"data": AdminResetPasswordResponseData(temporary_password=temporary_password)}


@router.post("/{user_id}/revoke-sessions", status_code=status.HTTP_204_NO_CONTENT)
def revoke_sessions(
    user_id: uuid.UUID, db: DbSession = Depends(get_db), admin: User = Depends(require_admin)
) -> None:
    user = service.get_user(db, user_id)
    service.revoke_sessions(db, user)
    record_audit_log(db, admin, "user.revoke_sessions", "user", user_id)


@router.patch("/{user_id}/plaid-access", response_model=Envelope[AdminUserPublic])
def update_plaid_access(
    user_id: uuid.UUID,
    body: AdminPlaidAccessUpdateRequest,
    db: DbSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict[str, AdminUserPublic]:
    user = service.get_user(db, user_id)
    updated = service.update_plaid_access(db, user, body.enabled, body.monthly_call_limit)
    record_audit_log(db, admin, "user.update_plaid_access", "user", user_id, body.model_dump())
    return {"data": service.to_public(db, updated)}


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: uuid.UUID,
    body: AdminUserDeleteRequest,
    db: DbSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> None:
    user = service.get_user(db, user_id)
    service.delete_user(db, user, body.confirm)
    # user_id (the path param), not user.id — `user` is a deleted/detached ORM instance
    # past this point and its attributes aren't safe to read.
    record_audit_log(db, admin, "user.delete", "user", user_id)
