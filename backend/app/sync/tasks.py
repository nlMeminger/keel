import uuid

import app.database as database
from app.auth.models import User
from app.banks import service as banks_service
from app.celery_app import celery_app
from app.jobs.service import run_job
from app.sync import service


@celery_app.task(name="sync.transactions")
def sync_transactions_task(job_id: str, user_id: str, bank_id: str | None) -> None:
    """Celery body for the `transaction_sync` job (API_SPEC.md §16), covering one bank or
    every bank the user has linked — resolves `database.SessionLocal` via module attribute
    (not a plain `from...import`) so tests running this synchronously under Celery's eager
    mode, with that attribute patched to the test database, route correctly."""

    def _run() -> dict[str, int]:
        db = database.SessionLocal()
        try:
            user = db.get(User, uuid.UUID(user_id))
            assert user is not None
            return service.sync_transactions_for_user(
                db, user, uuid.UUID(bank_id) if bank_id else None
            )
        finally:
            db.close()

    run_job(uuid.UUID(job_id), _run, session_factory=database.SessionLocal)


@celery_app.task(name="sync.balances")
def sync_balances_task(job_id: str, user_id: str, bank_id: str | None) -> None:
    """Celery body for the `balance_sync` job (API_SPEC.md §16) — refreshes account balances
    and investment holdings (banks_service.pull_accounts_and_holdings), not transactions."""

    def _run() -> dict[str, int]:
        db = database.SessionLocal()
        try:
            user = db.get(User, uuid.UUID(user_id))
            assert user is not None
            return service.sync_balances_for_user(db, user, uuid.UUID(bank_id) if bank_id else None)
        finally:
            db.close()

    run_job(uuid.UUID(job_id), _run, session_factory=database.SessionLocal)


@celery_app.task(name="sync.full_bank_sync")
def full_bank_sync_task(job_id: str, user_id: str, bank_id: str) -> None:
    """Celery body for `POST /banks/{bank_id}/sync` (API_SPEC.md §3) — still a
    `transaction_sync` job (API_SPEC.md §16's type list has no separate "full sync" entry),
    just one that also refreshes balances/holdings first since it's the one button a user
    has for "sync this bank now."""

    def _run() -> dict[str, int]:
        db = database.SessionLocal()
        try:
            user = db.get(User, uuid.UUID(user_id))
            assert user is not None
            bank, item = banks_service.get_bank_with_item(db, user, uuid.UUID(bank_id))
            return service.full_bank_sync(db, user, bank, item)
        finally:
            db.close()

    run_job(uuid.UUID(job_id), _run, session_factory=database.SessionLocal)
