import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from app.auth import service
from app.auth.models import User
from app.auth.schemas import (
    AccessTokenData,
    LoginRequest,
    LoginResponseData,
    MeUpdateRequest,
    RegisterRequest,
    SessionPublic,
    UserPublic,
)
from app.config import settings
from app.core.envelope import Envelope, single_page
from app.core.errors import AppError
from app.core.security import create_access_token, hash_token
from app.database import get_db
from app.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


class SuccessResponse(BaseModel):
    success: bool = True


def _set_refresh_cookie(response: Response, raw_token: str, expires_at: datetime) -> None:
    max_age = max(0, int((expires_at - datetime.now(UTC)).total_seconds()))
    response.set_cookie(
        key=service.REFRESH_COOKIE_NAME,
        value=raw_token,
        max_age=max_age,
        path=service.REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=service.REFRESH_COOKIE_NAME, path=service.REFRESH_COOKIE_PATH)


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/register", response_model=Envelope[UserPublic], status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: DbSession = Depends(get_db)) -> dict[str, UserPublic]:
    user = service.register_user(db, email=body.email, password=body.password, name=body.name)
    return {"data": UserPublic.model_validate(user)}


@router.post("/login", response_model=Envelope[LoginResponseData])
def login(
    body: LoginRequest, request: Request, response: Response, db: DbSession = Depends(get_db)
) -> dict[str, LoginResponseData]:
    user = service.authenticate_user(db, email=body.email, password=body.password)
    session, raw_token = service.create_session(
        db, user, user_agent=request.headers.get("user-agent"), ip_address=_client_ip(request)
    )
    _set_refresh_cookie(response, raw_token, session.expires_at)
    access_token = create_access_token(user.id)
    return {
        "data": LoginResponseData(access_token=access_token, user=UserPublic.model_validate(user))
    }


@router.post("/refresh", response_model=Envelope[AccessTokenData])
def refresh(
    request: Request, response: Response, db: DbSession = Depends(get_db)
) -> dict[str, AccessTokenData]:
    raw_token = request.cookies.get(service.REFRESH_COOKIE_NAME)
    if raw_token is None:
        raise AppError(401, "missing_refresh_token", "No refresh token provided.")
    user, session, raw_new_token = service.rotate_refresh_token(
        db, raw_token, user_agent=request.headers.get("user-agent"), ip_address=_client_ip(request)
    )
    _set_refresh_cookie(response, raw_new_token, session.expires_at)
    return {"data": AccessTokenData(access_token=create_access_token(user.id))}


@router.post("/logout", response_model=Envelope[SuccessResponse])
def logout(
    request: Request,
    response: Response,
    db: DbSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict[str, SuccessResponse]:
    raw_token = request.cookies.get(service.REFRESH_COOKIE_NAME)
    if raw_token is not None:
        service.revoke_session_by_token(db, raw_token)
    _clear_refresh_cookie(response)
    return {"data": SuccessResponse()}


@router.get("/sessions")
def list_sessions(
    request: Request, db: DbSession = Depends(get_db), user: User = Depends(get_current_user)
) -> dict[str, object]:
    raw_token = request.cookies.get(service.REFRESH_COOKIE_NAME)
    current_hash = hash_token(raw_token) if raw_token is not None else None
    sessions = service.list_active_sessions(db, user)
    items = [
        SessionPublic(
            id=s.id,
            created_at=s.issued_at,
            last_used_at=s.last_used_at,
            user_agent=s.user_agent,
            is_current=(s.token_hash == current_hash),
        )
        for s in sessions
    ]
    return single_page(items)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(
    session_id: uuid.UUID, db: DbSession = Depends(get_db), user: User = Depends(get_current_user)
) -> None:
    service.revoke_own_session(db, user, session_id)


@router.delete("/sessions", response_model=Envelope[SuccessResponse])
def revoke_other_sessions(
    request: Request, db: DbSession = Depends(get_db), user: User = Depends(get_current_user)
) -> dict[str, SuccessResponse]:
    raw_token = request.cookies.get(service.REFRESH_COOKIE_NAME)
    keep_hash = hash_token(raw_token) if raw_token is not None else None
    service.revoke_other_sessions(db, user, keep_hash)
    return {"data": SuccessResponse()}


@router.get("/me", response_model=Envelope[UserPublic])
def get_me(user: User = Depends(get_current_user)) -> dict[str, UserPublic]:
    return {"data": UserPublic.model_validate(user)}


@router.patch("/me", response_model=Envelope[UserPublic])
def update_me(
    body: MeUpdateRequest, db: DbSession = Depends(get_db), user: User = Depends(get_current_user)
) -> dict[str, UserPublic]:
    updated = service.update_profile(db, user, name=body.name, timezone=body.timezone)
    return {"data": UserPublic.model_validate(updated)}
