import uuid
from decimal import Decimal

from plaid.api.plaid_api import PlaidApi
from plaid.exceptions import ApiException
from plaid.model.account_base import AccountBase
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.investments_holdings_get_request import InvestmentsHoldingsGetRequest
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.accounts.models import Account
from app.auth.models import User
from app.banks.models import Bank, PlaidItem
from app.core.encryption import decrypt, encrypt
from app.core.errors import AppError
from app.core.plaid_client import ensure_plaid_enabled, get_plaid_client, plaid_error_to_app_error
from app.holdings.models import Holding


def get_bank(db: DbSession, user: User, bank_id: uuid.UUID) -> Bank:
    bank = db.scalar(select(Bank).where(Bank.id == bank_id, Bank.owner_id == user.id))
    if bank is None:
        raise AppError(404, "not_found", "Bank not found.")
    return bank


def get_bank_with_item(db: DbSession, user: User, bank_id: uuid.UUID) -> tuple[Bank, PlaidItem]:
    bank = get_bank(db, user, bank_id)
    item = db.get(PlaidItem, bank.plaid_item_id)
    assert item is not None  # FK guarantees this; Bank never outlives its PlaidItem.
    return bank, item


def create_bank_from_exchange(
    db: DbSession,
    user: User,
    access_token: str,
    item_id: str,
    institution_id: str,
    institution_name: str,
) -> tuple[Bank, PlaidItem]:
    """Persists a brand-new Bank/PlaidItem pair from a completed Link exchange
    (API_SPEC.md §2/§3). `access_token` is encrypted here — the one place a raw Plaid
    access_token exists outside Plaid's own systems is in memory, mid-request."""
    item = PlaidItem(
        access_token=encrypt(access_token),
        item_id=item_id,
        institution_id=institution_id,
        institution_name=institution_name,
    )
    db.add(item)
    db.flush()
    bank = Bank(owner_id=user.id, plaid_item_id=item.id)
    db.add(bank)
    db.commit()
    db.refresh(bank)
    db.refresh(item)
    return bank, item


def count_active_accounts(db: DbSession, bank_id: uuid.UUID) -> int:
    stmt = (
        select(func.count())
        .select_from(Account)
        .where(Account.bank_id == bank_id, Account.is_active.is_(True))
    )
    return db.scalar(stmt) or 0


def _map_account_type(plaid_type: str, plaid_subtype: str | None) -> str:
    """Maps Plaid's (type, subtype) onto our fixed ACCOUNT_TYPES set — a lossy mapping by
    necessity, since Plaid's subtype list (CD, HSA, money market, home equity, ...) is far
    finer-grained than the 7 types this app models."""
    if plaid_type == "credit":
        return "credit_card"
    if plaid_type in ("investment", "brokerage"):
        return "investment"
    if plaid_type == "loan":
        if plaid_subtype == "mortgage":
            return "mortgage"
        if plaid_subtype == "student":
            return "student_loan"
        return "loan"
    return "checking" if plaid_subtype == "checking" else "savings"


def _detail_for_account(account_type: str, plaid_account: AccountBase) -> dict[str, object]:
    """Best-effort `detail` from the basic Accounts product alone — credit limit/APR and
    loan terms need Plaid's Liabilities product, which this app doesn't integrate (not in
    SPEC.md's scope); omitted keys just mean an incomplete-but-valid `detail` for now."""
    if account_type == "credit_card" and plaid_account.balances.limit is not None:
        return {"credit_limit": plaid_account.balances.limit}
    if account_type == "investment":
        subtype = getattr(plaid_account.subtype, "value", None)
        if subtype is not None:
            return {"account_subtype": subtype}
    return {}


def pull_accounts_and_holdings(
    db: DbSession, user: User, bank: Bank, item: PlaidItem
) -> list[Account]:
    """Pulls the current account list (and, for any investment accounts, holdings) from
    Plaid and upserts them into the same Account/Holding tables Phase 4 built for manual
    entry — idempotent on Plaid's own account_id, so this is safe to call again on every
    later balance/transaction sync (7.4/7.5), not just once at link time."""
    ensure_plaid_enabled(user)
    client = get_plaid_client()
    access_token = decrypt(item.access_token)
    try:
        plaid_accounts = client.accounts_get(AccountsGetRequest(access_token=access_token)).accounts
    except ApiException as exc:
        raise plaid_error_to_app_error(exc) from exc

    accounts: list[Account] = []
    for plaid_account in plaid_accounts:
        plaid_type = plaid_account.type.value
        plaid_subtype = getattr(plaid_account.subtype, "value", None)
        account_type = _map_account_type(plaid_type, plaid_subtype)
        current_balance = plaid_account.balances.current
        balance = Decimal(str(current_balance)) if current_balance is not None else Decimal("0")

        existing = db.scalar(
            select(Account).where(Account.plaid_account_id == plaid_account.account_id)
        )
        if existing is not None:
            existing.name = plaid_account.name
            existing.balance = balance
            existing.bank_id = bank.id
            existing.is_active = True
            accounts.append(existing)
        else:
            account = Account(
                user_id=user.id,
                name=plaid_account.name,
                account_type=account_type,
                balance=balance,
                detail=_detail_for_account(account_type, plaid_account),
                is_plaid_linked=True,
                bank_id=bank.id,
                plaid_account_id=plaid_account.account_id,
            )
            db.add(account)
            accounts.append(account)
    db.commit()
    for account in accounts:
        db.refresh(account)

    investment_accounts = {
        a.plaid_account_id: a for a in accounts if a.account_type == "investment"
    }
    if investment_accounts:
        _pull_holdings(db, client, access_token, investment_accounts)

    return accounts


def _pull_holdings(
    db: DbSession,
    client: PlaidApi,
    access_token: str,
    investment_accounts: dict[str | None, Account],
) -> None:
    """Populates `Holding` rows (source='plaid', read-only — see app.holdings.service's
    403-on-Plaid-sourced checks) for every investment account just pulled above."""
    try:
        response = client.investments_holdings_get(
            InvestmentsHoldingsGetRequest(access_token=access_token)
        )
    except ApiException as exc:
        raise plaid_error_to_app_error(exc) from exc

    securities = {security.security_id: security for security in response.securities}
    for plaid_holding in response.holdings:
        account = investment_accounts.get(plaid_holding.account_id)
        if account is None:
            continue
        security = securities.get(plaid_holding.security_id)
        symbol = plaid_holding.security_id
        name = plaid_holding.security_id
        if security is not None:
            symbol = security.ticker_symbol or security.security_id
            name = security.name or symbol

        cost_basis = (
            Decimal(str(plaid_holding.cost_basis))
            if plaid_holding.cost_basis is not None
            else Decimal("0")
        )
        current_value = Decimal(str(plaid_holding.institution_value))
        quantity = Decimal(str(plaid_holding.quantity))

        existing_holding = db.scalar(
            select(Holding).where(
                Holding.account_id == account.id,
                Holding.security_id == plaid_holding.security_id,
            )
        )
        if existing_holding is not None:
            existing_holding.quantity = quantity
            existing_holding.cost_basis = cost_basis
            existing_holding.current_value = current_value
        else:
            db.add(
                Holding(
                    account_id=account.id,
                    security_id=plaid_holding.security_id,
                    symbol=symbol,
                    name=name,
                    quantity=quantity,
                    cost_basis=cost_basis,
                    current_value=current_value,
                    source="plaid",
                )
            )
    db.commit()
