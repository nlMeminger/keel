import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.auth.models import User
from app.banks.models import Bank, PlaidItem
from app.core.encryption import encrypt
from app.core.errors import AppError


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
