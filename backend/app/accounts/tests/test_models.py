import uuid
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session as OrmSession

from app.accounts.models import Account
from app.auth.models import User


def _make_user(db: OrmSession) -> User:
    user = User(email="owner@example.com", password_hash="hashed", name="Owner")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_checking_and_mortgage_persist_through_the_same_table(db: OrmSession) -> None:
    user = _make_user(db)
    checking = Account(
        user_id=user.id,
        name="Everyday checking",
        account_type="checking",
        balance=Decimal("1000.00"),
        detail={"overdraft_limit": 200},
    )
    mortgage = Account(
        user_id=user.id,
        name="Home loan",
        account_type="mortgage",
        balance=Decimal("250000.00"),
        detail={"principal": 260000, "interest_rate": 5.5, "term_months": 360},
    )
    db.add_all([checking, mortgage])
    db.commit()
    db.refresh(checking)
    db.refresh(mortgage)

    # No second query/join needed to read mortgage-specific fields straight off `detail`.
    assert mortgage.detail["principal"] == 260000
    assert mortgage.detail["term_months"] == 360
    assert checking.detail["overdraft_limit"] == 200
    assert {checking.account_type, mortgage.account_type} == {"checking", "mortgage"}


def test_account_defaults(db: OrmSession) -> None:
    user = _make_user(db)
    account = Account(
        user_id=user.id, name="New account", account_type="savings", balance=Decimal("0")
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    assert account.detail == {}
    assert account.is_active is True
    assert account.is_plaid_linked is False


def test_invalid_account_type_rejected_at_db_level(db: OrmSession) -> None:
    user = _make_user(db)
    account = Account(user_id=user.id, name="Bad type", account_type="bogus", balance=Decimal("0"))
    db.add(account)
    try:
        db.commit()
        raised = False
    except Exception:
        db.rollback()
        raised = True
    assert raised


def test_accounts_table_has_user_id_index(db: OrmSession) -> None:
    rows = db.execute(
        text("SELECT indexdef FROM pg_indexes WHERE tablename = 'accounts'")
    ).scalars()
    assert any("user_id" in indexdef for indexdef in rows)


def test_account_cascades_on_user_delete(db: OrmSession) -> None:
    user = _make_user(db)
    account = Account(user_id=user.id, name="Doomed", account_type="checking", balance=Decimal("0"))
    db.add(account)
    db.commit()
    account_id = account.id

    db.delete(user)
    db.commit()

    assert db.get(Account, account_id) is None


def test_account_id_is_uuid(db: OrmSession) -> None:
    user = _make_user(db)
    account = Account(
        user_id=user.id, name="Has uuid", account_type="checking", balance=Decimal("0")
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    assert isinstance(account.id, uuid.UUID)
