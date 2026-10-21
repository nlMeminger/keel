import pytest
from sqlalchemy.orm import Session as OrmSession

from app.auth.models import User
from app.core.errors import AppError
from app.core.plaid_client import ensure_plaid_enabled


def _make_user(db: OrmSession, plaid_enabled: bool) -> User:
    user = User(
        email=f"plaid-check-{plaid_enabled}@example.com",
        password_hash="hashed",
        name="Tester",
        plaid_enabled=plaid_enabled,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_ensure_plaid_enabled_passes_for_enabled_user(db: OrmSession) -> None:
    user = _make_user(db, plaid_enabled=True)
    ensure_plaid_enabled(user)  # must not raise


def test_ensure_plaid_enabled_raises_403_for_disabled_user(db: OrmSession) -> None:
    user = _make_user(db, plaid_enabled=False)
    with pytest.raises(AppError) as exc_info:
        ensure_plaid_enabled(user)
    assert exc_info.value.status_code == 403
