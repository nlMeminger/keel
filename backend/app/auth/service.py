import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session as DbSession

from app.auth.models import Session, User
from app.config import settings
from app.core.errors import AppError
from app.core.rate_limit import REFRESH_LIMIT, enforce_rate_limit
from app.core.security import generate_opaque_token, hash_password, hash_token, verify_password

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"


def register_user(db: DbSession, email: str, password: str, name: str) -> User:
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise AppError(409, "email_taken", "An account with this email already exists.")
    user = User(email=email, password_hash=hash_password(password), name=name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: DbSession, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(password, user.password_hash):
        raise AppError(401, "invalid_credentials", "Incorrect email or password.")
    if user.status != "active":
        raise AppError(403, "account_suspended", "This account is suspended.")
    return user


def _family_absolute_expiry(db: DbSession, family_id: uuid.UUID) -> datetime:
    family_created_at = db.scalar(
        select(func.min(Session.issued_at)).where(Session.family_id == family_id)
    )
    assert family_created_at is not None, "family_id always has at least one session row"
    return family_created_at + timedelta(days=settings.refresh_token_absolute_expire_days)


def _new_session_expiry(absolute_cap: datetime) -> datetime:
    sliding = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    return min(sliding, absolute_cap)


def create_session(
    db: DbSession, user: User, user_agent: str | None, ip_address: str | None
) -> tuple[Session, str]:
    """Starts a brand-new refresh-token family (login only — rotation stays within a family)."""
    family_id = uuid.uuid4()
    absolute_cap = datetime.now(UTC) + timedelta(days=settings.refresh_token_absolute_expire_days)
    raw_token = generate_opaque_token()
    session = Session(
        user_id=user.id,
        family_id=family_id,
        token_hash=hash_token(raw_token),
        expires_at=_new_session_expiry(absolute_cap),
        user_agent=user_agent,
        ip_address=ip_address,
    )
    db.add(session)
    user.last_login_at = datetime.now(UTC)
    db.commit()
    db.refresh(session)
    return session, raw_token


def _revoke_family(db: DbSession, family_id: uuid.UUID) -> None:
    now = datetime.now(UTC)
    db.execute(
        update(Session)
        .where(Session.family_id == family_id, Session.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.commit()


def rotate_refresh_token(
    db: DbSession, raw_token: str, user_agent: str | None, ip_address: str | None
) -> tuple[User, Session, str]:
    """Validates + rotates a refresh token.

    A replayed, already-revoked token revokes the whole family (theft detection).
    """
    token_hash = hash_token(raw_token)
    session = db.scalar(select(Session).where(Session.token_hash == token_hash))
    if session is None:
        raise AppError(401, "invalid_token", "Invalid refresh token.")

    if session.revoked_at is not None:
        # Theft detection always fires, even over the rate limit below — never silently
        # swallow a replayed/stolen token just because the attacker hit the request cap.
        _revoke_family(db, session.family_id)
        raise AppError(401, "session_revoked", "Session revoked. Please log in again.")

    enforce_rate_limit(f"ratelimit:refresh:{session.user_id}", *REFRESH_LIMIT)

    now = datetime.now(UTC)
    if session.expires_at < now:
        raise AppError(401, "expired_token", "Refresh token expired. Please log in again.")

    absolute_cap = _family_absolute_expiry(db, session.family_id)
    if now >= absolute_cap:
        _revoke_family(db, session.family_id)
        raise AppError(401, "session_expired", "Session expired. Please log in again.")

    session.revoked_at = now
    session.last_used_at = now

    raw_new_token = generate_opaque_token()
    new_session = Session(
        user_id=session.user_id,
        family_id=session.family_id,
        token_hash=hash_token(raw_new_token),
        expires_at=_new_session_expiry(absolute_cap),
        user_agent=user_agent,
        ip_address=ip_address,
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)

    user = db.get(User, session.user_id)
    assert user is not None
    return user, new_session, raw_new_token


def revoke_session_by_token(db: DbSession, raw_token: str) -> None:
    token_hash = hash_token(raw_token)
    session = db.scalar(select(Session).where(Session.token_hash == token_hash))
    if session is not None and session.revoked_at is None:
        session.revoked_at = datetime.now(UTC)
        db.commit()


def list_active_sessions(db: DbSession, user: User) -> list[Session]:
    now = datetime.now(UTC)
    return list(
        db.scalars(
            select(Session)
            .where(
                Session.user_id == user.id,
                Session.revoked_at.is_(None),
                Session.expires_at > now,
            )
            .order_by(Session.issued_at.desc())
        )
    )


def revoke_own_session(db: DbSession, user: User, session_id: uuid.UUID) -> None:
    session = db.scalar(select(Session).where(Session.id == session_id, Session.user_id == user.id))
    if session is None:
        raise AppError(404, "not_found", "Session not found.")
    if session.revoked_at is None:
        session.revoked_at = datetime.now(UTC)
        db.commit()


def revoke_other_sessions(db: DbSession, user: User, keep_token_hash: str | None) -> None:
    now = datetime.now(UTC)
    stmt = update(Session).where(Session.user_id == user.id, Session.revoked_at.is_(None))
    if keep_token_hash is not None:
        stmt = stmt.where(Session.token_hash != keep_token_hash)
    db.execute(stmt.values(revoked_at=now))
    db.commit()


def update_profile(db: DbSession, user: User, name: str | None, timezone: str | None) -> User:
    if name is not None:
        user.name = name
    if timezone is not None:
        user.timezone = timezone
    db.commit()
    db.refresh(user)
    return user
