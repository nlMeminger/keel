import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.auth.models import User
from scripts.bootstrap_admin import BootstrapAdminError, bootstrap_admin


def test_bootstrap_admin_creates_exactly_one_admin(db: DbSession) -> None:
    admin, generated_password = bootstrap_admin(db, "admin@example.com", "Admin", None)

    assert admin.role == "admin"
    assert generated_password is not None

    admins = db.scalars(select(User).where(User.role == "admin")).all()
    assert len(admins) == 1


def test_bootstrap_admin_refuses_a_second_admin(db: DbSession) -> None:
    bootstrap_admin(db, "first-admin@example.com", "First", "a-fixed-password")

    with pytest.raises(BootstrapAdminError):
        bootstrap_admin(db, "second-admin@example.com", "Second", "another-password")

    admins = db.scalars(select(User).where(User.role == "admin")).all()
    assert len(admins) == 1
    assert admins[0].email == "first-admin@example.com"


def test_bootstrap_admin_with_explicit_password_does_not_generate_one(db: DbSession) -> None:
    _admin, generated_password = bootstrap_admin(db, "admin2@example.com", "Admin", "my-password")
    assert generated_password is None
