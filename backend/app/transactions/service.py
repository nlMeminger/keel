import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, Select, select
from sqlalchemy.orm import Session as DbSession

from app.accounts.models import Account
from app.auth.models import User
from app.budgets import service as budgets_service
from app.categories.models import Category
from app.core.errors import AppError
from app.merchants.models import Merchant
from app.transactions.models import Transaction
from app.transactions.transfer import confirm_transfer, detect_transfer_candidates, reject_transfer


def _get_owned_account(db: DbSession, user: User, account_id: uuid.UUID) -> Account:
    account = db.scalar(select(Account).where(Account.id == account_id, Account.user_id == user.id))
    if account is None:
        raise AppError(404, "not_found", "Account not found.")
    return account


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


def create_transaction(
    db: DbSession,
    user: User,
    account_id: uuid.UUID,
    category_id: uuid.UUID | None,
    merchant_id: uuid.UUID | None,
    amount: Decimal,
    description: str,
    notes: str | None,
    txn_date: date,
    pending: bool,
) -> Transaction:
    _get_owned_account(db, user, account_id)
    _validate_category_visible(db, user, category_id)
    _validate_merchant_owned(db, user, merchant_id)

    txn = Transaction(
        user_id=user.id,
        account_id=account_id,
        category_id=category_id,
        merchant_id=merchant_id,
        amount=amount,
        description=description,
        notes=notes,
        date=txn_date,
        pending=pending,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)

    detect_transfer_candidates(db, txn)
    db.refresh(txn)
    budgets_service.notify_threshold_crossings_for_user(db, user)
    return txn


def get_transaction(db: DbSession, user: User, transaction_id: uuid.UUID) -> Transaction:
    txn = db.scalar(
        select(Transaction).where(Transaction.id == transaction_id, Transaction.user_id == user.id)
    )
    if txn is None:
        raise AppError(404, "not_found", "Transaction not found.")
    return txn


def _sort_clause(sort: str) -> ColumnElement[Any]:
    if sort == "date_asc":
        return Transaction.date.asc()
    if sort == "amount_asc":
        return Transaction.amount.asc()
    if sort == "amount_desc":
        return Transaction.amount.desc()
    return Transaction.date.desc()


def list_transactions_stmt(
    user: User,
    account_id: uuid.UUID | None,
    category_id: uuid.UUID | None,
    merchant: str | None,
    description: str | None,
    amount_min: Decimal | None,
    amount_max: Decimal | None,
    date_from: date | None,
    date_to: date | None,
    pending: bool | None,
    transfer_status: str | None,
    sort: str,
) -> Select[Transaction]:
    stmt = select(Transaction).where(Transaction.user_id == user.id)
    if account_id is not None:
        stmt = stmt.where(Transaction.account_id == account_id)
    if category_id is not None:
        stmt = stmt.where(Transaction.category_id == category_id)
    if merchant is not None:
        # Free-text substring search against the linked merchant's name — "merchant" (not
        # "merchant_id") is the signal this is meant as a search, unlike account_id/category_id.
        stmt = stmt.join(Merchant, Transaction.merchant_id == Merchant.id).where(
            Merchant.name.ilike(f"%{merchant}%")
        )
    if description is not None:
        stmt = stmt.where(Transaction.description.ilike(f"%{description}%"))
    if amount_min is not None:
        stmt = stmt.where(Transaction.amount >= amount_min)
    if amount_max is not None:
        stmt = stmt.where(Transaction.amount <= amount_max)
    if date_from is not None:
        stmt = stmt.where(Transaction.date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Transaction.date <= date_to)
    if pending is not None:
        stmt = stmt.where(Transaction.pending == pending)
    if transfer_status is not None:
        stmt = stmt.where(Transaction.transfer_status == transfer_status)
    return stmt.order_by(_sort_clause(sort))


def update_transaction(
    db: DbSession, user: User, transaction_id: uuid.UUID, fields: dict[str, object]
) -> Transaction:
    """`fields` comes from the request body's `model_dump(exclude_unset=True)` — only keys the
    client actually sent are present, so an omitted field is left untouched while an explicit
    null clears it (e.g. uncategorizing a transaction)."""
    txn = get_transaction(db, user, transaction_id)
    if "category_id" in fields:
        category_id = fields["category_id"]
        assert category_id is None or isinstance(category_id, uuid.UUID)
        _validate_category_visible(db, user, category_id)
        txn.category_id = category_id
    if "merchant_id" in fields:
        merchant_id = fields["merchant_id"]
        assert merchant_id is None or isinstance(merchant_id, uuid.UUID)
        _validate_merchant_owned(db, user, merchant_id)
        txn.merchant_id = merchant_id
    if "notes" in fields:
        notes = fields["notes"]
        assert notes is None or isinstance(notes, str)
        txn.notes = notes
    db.commit()

    # transfer_status resolves a pending suggestion (confirm/reject) — handled last since it
    # touches the paired transaction too, after this side's other fields are already saved.
    if fields.get("transfer_status") is not None:
        new_status = fields["transfer_status"]
        assert new_status in ("confirmed", "rejected")
        if txn.transfer_status != "suggested" or txn.paired_transaction_id is None:
            raise AppError(
                409,
                "no_transfer_suggestion",
                "This transaction has no pending transfer suggestion.",
            )
        paired = db.get(Transaction, txn.paired_transaction_id)
        assert paired is not None
        if new_status == "confirmed":
            confirm_transfer(db, txn, paired)
        else:
            reject_transfer(db, txn, paired)

    budgets_service.notify_threshold_crossings_for_user(db, user)
    db.refresh(txn)
    return txn


def delete_transaction(db: DbSession, user: User, transaction_id: uuid.UUID) -> None:
    txn = get_transaction(db, user, transaction_id)
    # Deleting one side of a suggested/confirmed pair must reset the other side's status —
    # the self-referential FK's ON DELETE SET NULL only clears paired_transaction_id, it
    # never touches transfer_status on the other row.
    if txn.transfer_status in ("suggested", "confirmed") and txn.paired_transaction_id is not None:
        paired = db.get(Transaction, txn.paired_transaction_id)
        if paired is not None:
            paired.transfer_status = "none"
            paired.paired_transaction_id = None
    db.delete(txn)
    db.commit()
