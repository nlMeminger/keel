import uuid

import pytest
from plaid.exceptions import ApiException
from sqlalchemy import select, text
from sqlalchemy.orm import Session as OrmSession

from app.auth.models import User
from app.banks.models import PlaidAPICall
from app.banks.service import call_plaid
from app.core.errors import AppError


def _make_user(db: OrmSession) -> User:
    user = User(email="call-log@example.com", password_hash="hashed", name="Tester")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_call_plaid_logs_one_success_row(db: OrmSession) -> None:
    user = _make_user(db)

    result = call_plaid(db, user.id, "accounts_get", lambda: "ok")

    assert result == "ok"
    rows = db.scalars(select(PlaidAPICall).where(PlaidAPICall.user_id == user.id)).all()
    assert len(rows) == 1
    assert rows[0].endpoint == "accounts_get"
    assert rows[0].status == "success"
    assert rows[0].error_code is None


def test_call_plaid_logs_one_error_row_and_raises_app_error(db: OrmSession) -> None:
    user = _make_user(db)

    def boom() -> None:
        raise ApiException(status=400, reason="Bad Request")

    with pytest.raises(AppError):
        call_plaid(db, user.id, "transactions_sync", boom)

    rows = db.scalars(select(PlaidAPICall).where(PlaidAPICall.user_id == user.id)).all()
    assert len(rows) == 1
    assert rows[0].endpoint == "transactions_sync"
    assert rows[0].status == "error"
    assert rows[0].error_code is not None


def test_call_plaid_logs_a_separate_row_per_call(db: OrmSession) -> None:
    user = _make_user(db)
    for _ in range(3):
        call_plaid(db, user.id, "accounts_get", lambda: "ok")

    rows = db.scalars(select(PlaidAPICall).where(PlaidAPICall.user_id == user.id)).all()
    assert len(rows) == 3


def test_plaid_api_calls_table_has_user_id_index(db: OrmSession) -> None:
    rows = db.execute(
        text("SELECT indexdef FROM pg_indexes WHERE tablename = 'plaid_api_calls'")
    ).scalars()
    indexdefs = list(rows)
    assert any("user_id" in i for i in indexdefs)
    assert any("created_at" in i for i in indexdefs)


def test_plaid_api_call_id_is_uuid(db: OrmSession) -> None:
    user = _make_user(db)
    call_plaid(db, user.id, "accounts_get", lambda: "ok")
    row = db.scalar(select(PlaidAPICall).where(PlaidAPICall.user_id == user.id))
    assert row is not None
    assert isinstance(row.id, uuid.UUID)
