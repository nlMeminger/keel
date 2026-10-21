import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session as DbSession

from app.accounts.models import Account
from app.auth.models import User
from app.categories.models import Category
from app.core.errors import AppError
from app.merchants.models import Merchant
from app.recurring_transactions.models import RecurringTransaction, RecurringTransactionPayment


def _validate_account_owned(db: DbSession, user: User, account_id: uuid.UUID | None) -> None:
    if account_id is None:
        return
    account = db.scalar(select(Account).where(Account.id == account_id, Account.user_id == user.id))
    if account is None:
        raise AppError(404, "not_found", "Account not found.")


def _validate_category_visible(db: DbSession, user: User, category_id: uuid.UUID | None) -> None:
    if category_id is None:
        return
    category = db.get(Category, category_id)
    if category is None or (category.owner_id is not None and category.owner_id != user.id):
        raise AppError(404, "not_found", "Category not found.")


def _validate_merchant_owned(db: DbSession, user: User, merchant_id: uuid.UUID | None) -> None:
    if merchant_id is None:
        return
    merchant = db.get(Merchant, merchant_id)
    if merchant is None or merchant.user_id != user.id:
        raise AppError(404, "not_found", "Merchant not found.")


def create_recurring(
    db: DbSession,
    user: User,
    name: str,
    amount_expected: Decimal,
    frequency: str,
    account_id: uuid.UUID | None,
    category_id: uuid.UUID | None,
    merchant_id: uuid.UUID | None,
    next_due_date: date | None,
    is_bill: bool,
) -> RecurringTransaction:
    _validate_account_owned(db, user, account_id)
    _validate_category_visible(db, user, category_id)
    _validate_merchant_owned(db, user, merchant_id)
    row = RecurringTransaction(
        user_id=user.id,
        name=name,
        amount_expected=amount_expected,
        frequency=frequency,
        account_id=account_id,
        category_id=category_id,
        merchant_id=merchant_id,
        next_due_date=next_due_date,
        is_bill=is_bill,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_recurring(db: DbSession, user: User, recurring_id: uuid.UUID) -> RecurringTransaction:
    row = db.scalar(
        select(RecurringTransaction).where(
            RecurringTransaction.id == recurring_id, RecurringTransaction.user_id == user.id
        )
    )
    if row is None:
        raise AppError(404, "not_found", "Recurring transaction not found.")
    return row


def list_recurring_stmt(user: User) -> Select[RecurringTransaction]:
    return (
        select(RecurringTransaction)
        .where(RecurringTransaction.user_id == user.id)
        .order_by(RecurringTransaction.created_at)
    )


def update_recurring(
    db: DbSession, user: User, recurring_id: uuid.UUID, fields: dict[str, object]
) -> RecurringTransaction:
    """`fields` comes from `model_dump(exclude_unset=True)` — an explicit null clears an
    optional link (e.g. unlinking a merchant); an omitted field is left untouched."""
    row = get_recurring(db, user, recurring_id)
    if "account_id" in fields:
        account_id = fields["account_id"]
        assert account_id is None or isinstance(account_id, uuid.UUID)
        _validate_account_owned(db, user, account_id)
        row.account_id = account_id
    if "category_id" in fields:
        category_id = fields["category_id"]
        assert category_id is None or isinstance(category_id, uuid.UUID)
        _validate_category_visible(db, user, category_id)
        row.category_id = category_id
    if "merchant_id" in fields:
        merchant_id = fields["merchant_id"]
        assert merchant_id is None or isinstance(merchant_id, uuid.UUID)
        _validate_merchant_owned(db, user, merchant_id)
        row.merchant_id = merchant_id
    if "name" in fields:
        name = fields["name"]
        assert isinstance(name, str)
        row.name = name
    if "amount_expected" in fields:
        amount_expected = fields["amount_expected"]
        assert isinstance(amount_expected, Decimal)
        row.amount_expected = amount_expected
    if "frequency" in fields:
        frequency = fields["frequency"]
        assert isinstance(frequency, str)
        row.frequency = frequency
    if "next_due_date" in fields:
        next_due_date = fields["next_due_date"]
        assert next_due_date is None or isinstance(next_due_date, date)
        row.next_due_date = next_due_date
    if "is_bill" in fields:
        is_bill = fields["is_bill"]
        assert isinstance(is_bill, bool)
        row.is_bill = is_bill
    db.commit()
    db.refresh(row)
    return row


def delete_recurring(db: DbSession, user: User, recurring_id: uuid.UUID) -> None:
    row = get_recurring(db, user, recurring_id)
    db.delete(row)
    db.commit()


def record_payment(
    db: DbSession, user: User, recurring_id: uuid.UUID, amount: Decimal, payment_date: date
) -> RecurringTransaction:
    """Ownership is checked once via the parent lookup; returns the updated parent (fresh
    `last_paid_date`) so the caller never needs a second fetch (API_SPEC.md §11)."""
    row = get_recurring(db, user, recurring_id)
    db.add(
        RecurringTransactionPayment(
            recurring_transaction_id=row.id, amount=amount, date=payment_date
        )
    )
    if row.last_paid_date is None or payment_date > row.last_paid_date:
        row.last_paid_date = payment_date
    db.commit()
    db.refresh(row)
    return row
