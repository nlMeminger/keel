import pytest
from sqlalchemy.orm import Session as OrmSession

from app.auth.models import User
from app.banks.models import PlaidAPICall
from app.core.errors import AppError
from app.core.plaid_client import ensure_plaid_enabled


def _make_user(db: OrmSession, plaid_enabled: bool, monthly_call_limit: int | None = None) -> User:
    user = User(
        email=f"plaid-check-{plaid_enabled}-{monthly_call_limit}@example.com",
        password_hash="hashed",
        name="Tester",
        plaid_enabled=plaid_enabled,
        plaid_monthly_call_limit=monthly_call_limit,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_ensure_plaid_enabled_passes_for_enabled_user(db: OrmSession) -> None:
    user = _make_user(db, plaid_enabled=True)
    ensure_plaid_enabled(db, user)  # must not raise


def test_ensure_plaid_enabled_raises_403_for_disabled_user(db: OrmSession) -> None:
    user = _make_user(db, plaid_enabled=False)
    with pytest.raises(AppError) as exc_info:
        ensure_plaid_enabled(db, user)
    assert exc_info.value.status_code == 403


def test_ensure_plaid_enabled_passes_under_monthly_call_limit(db: OrmSession) -> None:
    user = _make_user(db, plaid_enabled=True, monthly_call_limit=2)
    db.add(PlaidAPICall(user_id=user.id, endpoint="accounts_get", status="success"))
    db.commit()
    ensure_plaid_enabled(db, user)  # 1 call logged, limit is 2 — must not raise


def test_ensure_plaid_enabled_raises_429_at_monthly_call_limit(db: OrmSession) -> None:
    user = _make_user(db, plaid_enabled=True, monthly_call_limit=2)
    for _ in range(2):
        db.add(PlaidAPICall(user_id=user.id, endpoint="accounts_get", status="success"))
    db.commit()
    with pytest.raises(AppError) as exc_info:
        ensure_plaid_enabled(db, user)
    assert exc_info.value.status_code == 429


def test_ensure_plaid_enabled_unlimited_by_default(db: OrmSession) -> None:
    """Default plaid_monthly_call_limit=None means unlimited (SPEC.md §5) — never blocks
    regardless of how many calls have already been logged."""
    user = _make_user(db, plaid_enabled=True, monthly_call_limit=None)
    for _ in range(5):
        db.add(PlaidAPICall(user_id=user.id, endpoint="accounts_get", status="success"))
    db.commit()
    ensure_plaid_enabled(db, user)  # must not raise
