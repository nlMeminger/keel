from sqlalchemy import text
from sqlalchemy.orm import Session as OrmSession

from app.auth.models import User


def test_user_defaults(db: OrmSession) -> None:
    user = User(email="new@example.com", password_hash="hashed", name="New User")
    db.add(user)
    db.commit()
    db.refresh(user)

    assert user.role == "user"
    assert user.status == "active"
    assert user.plaid_enabled is True
    assert user.plaid_monthly_call_limit is None
    assert user.must_change_password is False
    assert user.timezone == "UTC"


def test_sessions_table_has_token_hash_index(db: OrmSession) -> None:
    rows = db.execute(
        text("SELECT indexdef FROM pg_indexes WHERE tablename = 'sessions'")
    ).scalars()
    assert any("token_hash" in indexdef for indexdef in rows)
