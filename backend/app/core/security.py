import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.config import settings
from app.core.errors import AppError


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_access_token(user_id: uuid.UUID) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_signing_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, settings.jwt_signing_key, algorithms=[settings.jwt_algorithm])
    except jwt.InvalidTokenError as exc:
        raise AppError(401, "invalid_token", "Invalid or expired access token.") from exc
    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise AppError(401, "invalid_token", "Invalid or expired access token.") from exc


def generate_opaque_token() -> str:
    """High-entropy random token for refresh tokens / API tokens — never a user-chosen secret."""
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """One-way hash for opaque tokens (refresh/API tokens): verify-only, raw value never reused."""
    return hashlib.sha256(token.encode()).hexdigest()
