"""Covers the retry scenario ROADMAP 7.10 asks for directly: a Bank row whose PlaidItem is
already marked removed_at (e.g. a prior attempt committed that but crashed before deleting
the Bank row) must not trigger a second real Plaid item/remove call — Plaid itself errors
(ITEM_NOT_FOUND) on a repeat removal of the same access_token."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.accounts.models import Account
from app.auth.models import User
from app.banks.models import Bank, PlaidAPICall, PlaidItem
from app.banks.service import unlink_bank


def _make_user(db: OrmSession) -> User:
    user = User(email="unlink-idempotent@example.com", password_hash="hashed", name="Tester")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_unlinking_an_already_removed_item_skips_the_plaid_call(db: OrmSession) -> None:
    user = _make_user(db)
    item = PlaidItem(
        access_token="irrelevant",
        item_id=f"item-{uuid.uuid4()}",
        institution_id="ins_1",
        institution_name="Sandbox Bank",
        removed_at=datetime.now(UTC),
    )
    db.add(item)
    db.flush()
    bank = Bank(owner_id=user.id, plaid_item_id=item.id)
    db.add(bank)
    db.commit()
    bank_id = bank.id

    unlink_bank(db, user, bank_id)

    assert db.get(Bank, bank_id) is None
    assert (
        db.scalars(select(PlaidAPICall).where(PlaidAPICall.endpoint == "item_remove")).all() == []
    )


def test_unlinking_deactivates_and_unlinks_its_accounts(db: OrmSession) -> None:
    user = _make_user(db)
    item = PlaidItem(
        access_token="irrelevant",
        item_id=f"item-{uuid.uuid4()}",
        institution_id="ins_1",
        institution_name="Sandbox Bank",
        removed_at=datetime.now(UTC),
    )
    db.add(item)
    db.flush()
    bank = Bank(owner_id=user.id, plaid_item_id=item.id)
    db.add(bank)
    db.flush()
    account = Account(
        user_id=user.id,
        name="Plaid Checking",
        account_type="checking",
        balance=0,
        is_plaid_linked=True,
        bank_id=bank.id,
        plaid_account_id="plaid-acc-1",
    )
    db.add(account)
    db.commit()
    account_id = account.id

    unlink_bank(db, user, bank.id)

    db.expire_all()
    refreshed = db.get(Account, account_id)
    assert refreshed is not None
    assert refreshed.is_active is False
    assert refreshed.bank_id is None
    assert refreshed.is_plaid_linked is True  # provenance marker, unchanged by unlinking
