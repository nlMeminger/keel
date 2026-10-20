from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session as OrmSession

from app.accounts.models import Account
from app.auth.models import User
from app.transactions.models import Transaction


def _make_user_and_account(db: OrmSession) -> tuple[User, Account]:
    user = User(email="txn-owner@example.com", password_hash="hashed", name="Owner")
    db.add(user)
    db.commit()
    db.refresh(user)
    account = Account(
        user_id=user.id, name="Checking", account_type="checking", balance=Decimal("0")
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return user, account


def test_amount_sign_persists_for_inflow_and_outflow(db: OrmSession) -> None:
    user, account = _make_user_and_account(db)
    income = Transaction(
        user_id=user.id,
        account_id=account.id,
        amount=Decimal("500.00"),
        description="Paycheck",
        date=date(2026, 1, 15),
    )
    expense = Transaction(
        user_id=user.id,
        account_id=account.id,
        amount=Decimal("-42.50"),
        description="Groceries",
        date=date(2026, 1, 16),
    )
    db.add_all([income, expense])
    db.commit()
    db.refresh(income)
    db.refresh(expense)

    assert income.amount == Decimal("500.00")
    assert expense.amount == Decimal("-42.50")


def test_transaction_defaults(db: OrmSession) -> None:
    user, account = _make_user_and_account(db)
    txn = Transaction(
        user_id=user.id,
        account_id=account.id,
        amount=Decimal("-10.00"),
        description="Coffee",
        date=date(2026, 1, 1),
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)

    assert txn.pending is False
    assert txn.is_transfer is False
    assert txn.transfer_status == "none"
    assert txn.category_id is None
    assert txn.merchant_id is None
    assert txn.paired_transaction_id is None


def test_invalid_transfer_status_rejected_at_db_level(db: OrmSession) -> None:
    user, account = _make_user_and_account(db)
    txn = Transaction(
        user_id=user.id,
        account_id=account.id,
        amount=Decimal("-1.00"),
        description="Bad status",
        date=date(2026, 1, 1),
        transfer_status="bogus",
    )
    db.add(txn)
    try:
        db.commit()
        raised = False
    except Exception:
        db.rollback()
        raised = True
    assert raised


def test_transaction_cascades_on_account_delete(db: OrmSession) -> None:
    user, account = _make_user_and_account(db)
    txn = Transaction(
        user_id=user.id,
        account_id=account.id,
        amount=Decimal("-1.00"),
        description="Doomed",
        date=date(2026, 1, 1),
    )
    db.add(txn)
    db.commit()
    txn_id = txn.id

    db.delete(account)
    db.commit()

    assert db.get(Transaction, txn_id) is None


def test_paired_transaction_self_reference(db: OrmSession) -> None:
    user, account = _make_user_and_account(db)
    other_account = Account(
        user_id=user.id, name="Savings", account_type="savings", balance=Decimal("0")
    )
    db.add(other_account)
    db.commit()
    db.refresh(other_account)

    first = Transaction(
        user_id=user.id,
        account_id=account.id,
        amount=Decimal("-100.00"),
        description="Transfer out",
        date=date(2026, 1, 1),
    )
    db.add(first)
    db.commit()
    db.refresh(first)

    second = Transaction(
        user_id=user.id,
        account_id=other_account.id,
        amount=Decimal("100.00"),
        description="Transfer in",
        date=date(2026, 1, 1),
        paired_transaction_id=first.id,
    )
    db.add(second)
    db.commit()
    db.refresh(second)

    assert second.paired_transaction_id == first.id

    # Deleting the paired side SET NULLs this side's pointer rather than erroring.
    db.delete(first)
    db.commit()
    db.refresh(second)
    assert second.paired_transaction_id is None
