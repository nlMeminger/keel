from sqlalchemy.orm import Session

from app.auth.models import User


def test_user_defaults(db: Session) -> None:
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
