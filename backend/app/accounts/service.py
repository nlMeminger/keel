import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session as DbSession

from app.accounts.models import Account
from app.accounts.schemas import validate_detail_for_type
from app.auth.models import User
from app.core.errors import AppError
from app.metrics import service as metrics_service


def create_account(
    db: DbSession,
    user: User,
    name: str,
    account_type: str,
    balance: Decimal,
    detail: dict[str, object],
) -> Account:
    account = Account(
        user_id=user.id, name=name, account_type=account_type, balance=balance, detail=detail
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def get_account(db: DbSession, user: User, account_id: uuid.UUID) -> Account:
    account = db.scalar(select(Account).where(Account.id == account_id, Account.user_id == user.id))
    if account is None:
        raise AppError(404, "not_found", "Account not found.")
    return account


def list_accounts_stmt(
    user: User,
    account_type: str | None,
    active: bool | None,
    bank_id: uuid.UUID | None = None,
) -> Select[Account]:
    stmt = select(Account).where(Account.user_id == user.id)
    if account_type is not None:
        stmt = stmt.where(Account.account_type == account_type)
    if bank_id is not None:
        stmt = stmt.where(Account.bank_id == bank_id)
    if active is not None:
        stmt = stmt.where(Account.is_active == active)
    else:
        stmt = stmt.where(Account.is_active.is_(True))
    return stmt.order_by(Account.created_at)


def update_account(
    db: DbSession,
    user: User,
    account_id: uuid.UUID,
    name: str | None,
    account_type: str | None,
    balance: Decimal | None,
    detail: dict[str, object] | None,
) -> Account:
    account = get_account(db, user, account_id)
    balance_changed = balance is not None and balance != account.balance

    if name is not None:
        account.name = name
    if account_type is not None:
        account.account_type = account_type
    if balance is not None:
        account.balance = balance
    if detail is not None:
        account.detail = detail

    try:
        account.detail = validate_detail_for_type(account.account_type, account.detail)
    except ValueError as exc:
        raise AppError(422, "invalid_account_detail", str(exc)) from exc

    db.commit()
    db.refresh(account)

    # Append-only value-history entry (4.9) — never a find-and-update, and only written
    # when the submitted balance actually differs from what was already stored.
    if balance_changed:
        metrics_service.create_metric(
            db,
            user,
            metric_type="account_balance",
            value=account.balance,
            metric_date=datetime.now(UTC).date(),
            note=None,
            account_id=account.id,
            asset_id=None,
        )

    return account


def deactivate_account(db: DbSession, user: User, account_id: uuid.UUID) -> None:
    account = get_account(db, user, account_id)
    account.is_active = False
    db.commit()
