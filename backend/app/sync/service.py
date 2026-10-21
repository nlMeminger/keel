import uuid
from datetime import UTC, datetime
from decimal import Decimal

from plaid.model.transactions_sync_request import TransactionsSyncRequest
from plaid.model.transactions_sync_response import TransactionsSyncResponse
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.accounts.models import Account
from app.auth.models import User
from app.banks import service as banks_service
from app.banks.models import Bank, PlaidItem
from app.core.encryption import decrypt
from app.core.plaid_client import ensure_plaid_enabled, get_plaid_client
from app.transactions.models import Transaction
from app.transactions.transfer import detect_transfer_candidates


def _user_banks(db: DbSession, user: User, bank_id: uuid.UUID | None) -> list[Bank]:
    """Resolves the scope of a `/sync/*` call: one owned bank if `bank_id` is given (404 if
    it isn't the caller's), otherwise every bank the caller has linked."""
    if bank_id is not None:
        return [banks_service.get_bank(db, user, bank_id)]
    return list(db.scalars(select(Bank).where(Bank.owner_id == user.id)))


def sync_transactions_for_bank(
    db: DbSession, user: User, bank: Bank, item: PlaidItem
) -> dict[str, int]:
    """Calls Plaid's /transactions/sync in a cursor loop until has_more is false, upserting
    added/modified/removed transactions into the shared Transaction table — Plaid signs
    positive=outflow, the opposite of this app's convention (SPEC.md §5), so every amount is
    flipped on the way in. Persists the new cursor on PlaidItem once the loop completes."""
    ensure_plaid_enabled(user)
    client = get_plaid_client()
    access_token = decrypt(item.access_token)
    account_map = {
        account.plaid_account_id: account
        for account in db.scalars(select(Account).where(Account.bank_id == bank.id))
    }

    added = modified = removed = 0
    cursor = item.cursor
    while True:
        # The SDK rejects an explicit cursor=None — omit the kwarg entirely on the first
        # sync for this Item, per Plaid's "omit cursor to retrieve full history" guidance.
        cursor_kwargs: dict[str, str] = {"cursor": cursor} if cursor is not None else {}

        def _sync_page(kwargs: dict[str, str] = cursor_kwargs) -> TransactionsSyncResponse:
            return client.transactions_sync(
                TransactionsSyncRequest(access_token=access_token, **kwargs)
            )

        response = banks_service.call_plaid(db, user.id, "transactions_sync", _sync_page)

        for plaid_txn in response.added:
            account = account_map.get(plaid_txn.account_id)
            if account is None:
                continue
            existing = db.scalar(
                select(Transaction).where(
                    Transaction.plaid_transaction_id == plaid_txn.transaction_id
                )
            )
            if existing is not None:
                continue
            txn = Transaction(
                user_id=bank.owner_id,
                account_id=account.id,
                amount=-Decimal(str(plaid_txn.amount)),
                description=plaid_txn.merchant_name or plaid_txn.name,
                date=plaid_txn.date,
                pending=plaid_txn.pending,
                plaid_transaction_id=plaid_txn.transaction_id,
            )
            db.add(txn)
            db.flush()
            detect_transfer_candidates(db, txn)
            added += 1

        for plaid_txn in response.modified:
            existing = db.scalar(
                select(Transaction).where(
                    Transaction.plaid_transaction_id == plaid_txn.transaction_id
                )
            )
            if existing is None:
                continue
            existing.amount = -Decimal(str(plaid_txn.amount))
            existing.description = plaid_txn.merchant_name or plaid_txn.name
            existing.date = plaid_txn.date
            existing.pending = plaid_txn.pending
            modified += 1

        for removed_txn in response.removed:
            existing = db.scalar(
                select(Transaction).where(
                    Transaction.plaid_transaction_id == removed_txn.transaction_id
                )
            )
            if existing is not None:
                db.delete(existing)
                removed += 1

        cursor = response.next_cursor
        db.commit()
        if not response.has_more:
            break

    item.cursor = cursor
    bank.last_synced_at = datetime.now(UTC)
    db.commit()
    return {"added": added, "modified": modified, "removed": removed}


def sync_transactions_for_user(
    db: DbSession, user: User, bank_id: uuid.UUID | None
) -> dict[str, int]:
    totals = {"added": 0, "modified": 0, "removed": 0}
    for bank in _user_banks(db, user, bank_id):
        item = db.get(PlaidItem, bank.plaid_item_id)
        assert item is not None
        result = sync_transactions_for_bank(db, user, bank, item)
        for key, value in result.items():
            totals[key] += value
    return totals


def sync_balances_for_user(db: DbSession, user: User, bank_id: uuid.UUID | None) -> dict[str, int]:
    accounts_synced = 0
    for bank in _user_banks(db, user, bank_id):
        item = db.get(PlaidItem, bank.plaid_item_id)
        assert item is not None
        accounts_synced += len(banks_service.pull_accounts_and_holdings(db, user, bank, item))
        bank.last_synced_at = datetime.now(UTC)
        db.commit()
    return {"accounts_synced": accounts_synced}


def full_bank_sync(db: DbSession, user: User, bank: Bank, item: PlaidItem) -> dict[str, int]:
    """POST /banks/{bank_id}/sync (API_SPEC.md §3) — the per-bank "Sync now" action refreshes
    both balances/holdings and transactions in one job, rather than making the user trigger
    two separate syncs for one button."""
    accounts_synced = len(banks_service.pull_accounts_and_holdings(db, user, bank, item))
    transaction_result = sync_transactions_for_bank(db, user, bank, item)
    return {"accounts_synced": accounts_synced, **transaction_result}


def _active_banks_with_owners(db: DbSession) -> list[tuple[Bank, PlaidItem, User]]:
    """Every non-removed bank in the system, across every user — the scope Celery beat's
    scheduled sync runs over (API_SPEC.md §16), as opposed to one user's own banks."""
    rows = []
    for bank in db.scalars(select(Bank)):
        item = db.get(PlaidItem, bank.plaid_item_id)
        assert item is not None
        if item.removed_at is not None:
            continue
        owner = db.get(User, bank.owner_id)
        assert owner is not None
        rows.append((bank, item, owner))
    return rows


def sync_all_banks_transactions(db: DbSession) -> dict[str, int]:
    """Celery beat's scheduled `sync_transactions` run (API_SPEC.md §16) — every bank in the
    system, skipping (not erroring on) any owner with Plaid access disabled, so one
    admin-disabled user never blocks the scheduled run for everyone else."""
    totals = {"added": 0, "modified": 0, "removed": 0, "skipped_disabled": 0}
    for bank, item, owner in _active_banks_with_owners(db):
        if not owner.plaid_enabled:
            totals["skipped_disabled"] += 1
            continue
        result = sync_transactions_for_bank(db, owner, bank, item)
        for key in ("added", "modified", "removed"):
            totals[key] += result[key]
    return totals


def sync_all_banks_balances(db: DbSession) -> dict[str, int]:
    """Celery beat's scheduled `update_balances` run (API_SPEC.md §16) — same system-wide
    scope and disabled-owner skip as sync_all_banks_transactions above."""
    accounts_synced = 0
    skipped_disabled = 0
    for bank, item, owner in _active_banks_with_owners(db):
        if not owner.plaid_enabled:
            skipped_disabled += 1
            continue
        accounts_synced += len(banks_service.pull_accounts_and_holdings(db, owner, bank, item))
        bank.last_synced_at = datetime.now(UTC)
        db.commit()
    return {"accounts_synced": accounts_synced, "skipped_disabled": skipped_disabled}
