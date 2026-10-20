import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.categories.models import TRANSFER_CATEGORY_NAME, Category
from app.transactions.models import Transaction

MAX_BUSINESS_DAY_OFFSET = 2


def _business_day_window_dates(
    center: date, max_offset: int = MAX_BUSINESS_DAY_OFFSET
) -> list[date]:
    """Every calendar date within ±max_offset business days of center, stepping over
    weekends (no holiday calendar — a deliberate simplification)."""
    dates = [center]
    forward = center
    steps = 0
    while steps < max_offset:
        forward += timedelta(days=1)
        if forward.weekday() < 5:
            steps += 1
            dates.append(forward)
    backward = center
    steps = 0
    while steps < max_offset:
        backward -= timedelta(days=1)
        if backward.weekday() < 5:
            steps += 1
            dates.append(backward)
    return dates


def detect_transfer_candidates(db: DbSession, new_txn: Transaction) -> None:
    """Inline on POST /transactions (API_SPEC.md §5) — one bounded, indexed query against
    the user's OTHER accounts. Scoped by new_txn.user_id, so a different user's accounts
    are never candidates even when amount/date coincidentally match."""
    window_dates = _business_day_window_dates(new_txn.date)
    candidates = db.scalars(
        select(Transaction).where(
            Transaction.user_id == new_txn.user_id,
            Transaction.account_id != new_txn.account_id,
            Transaction.amount == -new_txn.amount,
            Transaction.date.in_(window_dates),
            Transaction.transfer_status == "none",
            Transaction.is_transfer.is_(False),
        )
    ).all()
    if not candidates:
        return

    # Tie-break on multiple candidates: closest date, then most-recently-created.
    best = min(
        candidates, key=lambda c: (abs((c.date - new_txn.date).days), -c.created_at.timestamp())
    )
    new_txn.paired_transaction_id = best.id
    new_txn.transfer_status = "suggested"
    best.paired_transaction_id = new_txn.id
    best.transfer_status = "suggested"
    db.commit()


def _transfer_category_id(db: DbSession) -> uuid.UUID:
    category = db.scalar(
        select(Category).where(
            Category.owner_id.is_(None), Category.primary_category == TRANSFER_CATEGORY_NAME
        )
    )
    assert category is not None, "the Transfer system category is always seeded"
    return category.id


def confirm_transfer(db: DbSession, txn: Transaction, paired: Transaction) -> None:
    transfer_category_id = _transfer_category_id(db)
    for side in (txn, paired):
        side.is_transfer = True
        side.transfer_status = "confirmed"
        side.category_id = transfer_category_id
    db.commit()


def reject_transfer(db: DbSession, txn: Transaction, paired: Transaction) -> None:
    """Clears both sides so the same pair is never re-suggested (detection's transfer_status
    == 'none' guard excludes anything already rejected)."""
    for side in (txn, paired):
        side.paired_transaction_id = None
        side.transfer_status = "rejected"
    db.commit()
