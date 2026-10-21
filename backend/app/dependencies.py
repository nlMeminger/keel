from datetime import UTC, datetime

from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin.models import ApiToken
from app.auth.models import User
from app.core.errors import AppError
from app.core.rate_limit import API_TOKEN_LIMIT, enforce_rate_limit
from app.core.security import decode_access_token, hash_token
from app.database import get_db

bearer_scheme = HTTPBearer(auto_error=False)


class PaginationParams(BaseModel):
    page: int
    page_size: int


def pagination_params(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
) -> PaginationParams:
    """Shared `?page=&page_size=` dependency for every real (non-`single_page`) list route."""
    return PaginationParams(page=page, page_size=page_size)


def _authenticate_api_token(db: Session, request: Request, raw_token: str) -> User:
    """Falls back here when `raw_token` doesn't decode as a user's own JWT (API_SPEC.md
    §18) — resolves to the token's bound user_id, enforces its own 60 req/min rate limit
    (independent of the Plaid monthly-call cap) and its read/read+write scope via the
    request's HTTP method (API_SPEC.md Conventions: "reads are GET, writes are
    POST/PATCH/DELETE"), and never grants admin-level access regardless of who issued it."""
    token_hash = hash_token(raw_token)
    api_token = db.scalar(select(ApiToken).where(ApiToken.token_hash == token_hash))
    now = datetime.now(UTC)
    if (
        api_token is None
        or api_token.revoked_at is not None
        or (api_token.expires_at is not None and api_token.expires_at < now)
    ):
        raise AppError(401, "unauthorized", "Invalid or expired token.")

    enforce_rate_limit(f"ratelimit:api_token:{api_token.id}", *API_TOKEN_LIMIT)
    if request.method != "GET" and "write" not in api_token.scopes:
        raise AppError(403, "read_only_token", "This token is read-only.")

    user = db.get(User, api_token.user_id)
    if user is None or user.status != "active":
        raise AppError(401, "unauthorized", "Invalid or expired token.")

    api_token.last_used_at = now
    db.commit()
    return user


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the acting user from the verified JWT, or an admin-issued API token
    (API_SPEC.md §18) when the bearer value doesn't decode as a JWT.

    Every write route's ownership check starts here — never trust a client-supplied
    user_id, this is the only source of truth for "who is calling."
    """
    if credentials is None:
        raise AppError(401, "unauthorized", "Missing or invalid Authorization header.")
    try:
        user_id = decode_access_token(credentials.credentials)
    except AppError:
        return _authenticate_api_token(db, request, credentials.credentials)
    user = db.get(User, user_id)
    if user is None or user.status != "active":
        raise AppError(401, "unauthorized", "Invalid or expired token.")
    return user
