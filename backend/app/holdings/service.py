import uuid
from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session as DbSession

from app.accounts import service as accounts_service
from app.accounts.models import Account
from app.auth.models import User
from app.core.errors import AppError
from app.holdings.models import Holding


def _get_investment_account(db: DbSession, user: User, account_id: uuid.UUID) -> Account:
    account = accounts_service.get_account(db, user, account_id)
    if account.account_type != "investment":
        raise AppError(
            422, "not_investment_account", "Holdings are only valid for investment accounts."
        )
    return account


def create_holding(
    db: DbSession,
    user: User,
    account_id: uuid.UUID,
    symbol: str,
    name: str,
    quantity: Decimal,
    cost_basis: Decimal,
) -> Holding:
    account = _get_investment_account(db, user, account_id)
    if account.is_plaid_linked:
        raise AppError(
            403, "plaid_linked_account", "Holdings on a Plaid-linked account are sync-populated."
        )
    holding = Holding(
        account_id=account.id, symbol=symbol, name=name, quantity=quantity, cost_basis=cost_basis
    )
    db.add(holding)
    db.commit()
    db.refresh(holding)
    return holding


def get_holding(db: DbSession, user: User, account_id: uuid.UUID, holding_id: uuid.UUID) -> Holding:
    account = _get_investment_account(db, user, account_id)
    holding = db.scalar(
        select(Holding).where(Holding.id == holding_id, Holding.account_id == account.id)
    )
    if holding is None:
        raise AppError(404, "not_found", "Holding not found.")
    return holding


def list_holdings_stmt(db: DbSession, user: User, account_id: uuid.UUID) -> Select[Holding]:
    account = _get_investment_account(db, user, account_id)
    return select(Holding).where(Holding.account_id == account.id).order_by(Holding.created_at)


def update_holding(
    db: DbSession,
    user: User,
    account_id: uuid.UUID,
    holding_id: uuid.UUID,
    symbol: str | None,
    name: str | None,
    quantity: Decimal | None,
    cost_basis: Decimal | None,
    current_value: Decimal | None,
) -> Holding:
    holding = get_holding(db, user, account_id, holding_id)
    if holding.source == "plaid":
        raise AppError(403, "plaid_sourced_holding", "Plaid-sourced holdings are read-only.")
    if symbol is not None:
        holding.symbol = symbol
    if name is not None:
        holding.name = name
    if quantity is not None:
        holding.quantity = quantity
    if cost_basis is not None:
        holding.cost_basis = cost_basis
    if current_value is not None:
        holding.current_value = current_value
    db.commit()
    db.refresh(holding)
    return holding


def delete_holding(db: DbSession, user: User, account_id: uuid.UUID, holding_id: uuid.UUID) -> None:
    holding = get_holding(db, user, account_id, holding_id)
    if holding.source == "plaid":
        raise AppError(403, "plaid_sourced_holding", "Plaid-sourced holdings are read-only.")
    db.delete(holding)
    db.commit()
