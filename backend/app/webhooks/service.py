import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.banks.models import Bank, PlaidItem
from app.jobs.service import create_job
from app.sync.tasks import full_bank_sync_task

logger = logging.getLogger("app.webhooks")

# ITEM webhook_codes that mean "this item needs the user to go through Link again."
_NEEDS_REAUTH_CODES = ("PENDING_EXPIRATION", "PENDING_DISCONNECT")


def handle_webhook(db: DbSession, payload: dict[str, Any]) -> dict[str, str]:
    """Dispatches a verified Plaid webhook (API_SPEC.md §17) to its side effect. Called only
    after verify_webhook has already confirmed authenticity — nothing here re-checks that."""
    item_id = payload.get("item_id")
    webhook_type = payload.get("webhook_type")
    webhook_code = payload.get("webhook_code")
    if not isinstance(item_id, str):
        return {"status": "ignored", "reason": "missing item_id"}

    item = db.scalar(select(PlaidItem).where(PlaidItem.item_id == item_id))
    if item is None:
        return {"status": "ignored", "reason": "unknown item_id"}

    # Ghost-item check: Plaid is still sending webhooks — and likely still billing — for an
    # item this app already explicitly removed. Checked before anything else below, since a
    # removed item's Bank row may not even exist anymore (7.10 deletes it).
    if item.removed_at is not None:
        logger.error(
            "Received %s/%s webhook for already-removed Plaid item %s",
            webhook_type,
            webhook_code,
            item_id,
        )
        return {"status": "ghost_item_alert"}

    bank = db.scalar(select(Bank).where(Bank.plaid_item_id == item.id))
    if bank is None:
        return {"status": "ignored", "reason": "no bank for item"}

    if webhook_type == "TRANSACTIONS" and webhook_code == "SYNC_UPDATES_AVAILABLE":
        job = create_job(db, "transaction_sync", owner_id=bank.owner_id)
        full_bank_sync_task.delay(str(job.id), str(bank.owner_id), str(bank.id))
        return {"status": "sync_enqueued", "job_id": str(job.id)}

    if webhook_type == "ITEM":
        if webhook_code == "ERROR":
            error = payload.get("error")
            error_code = error.get("error_code") if isinstance(error, dict) else None
            bank.health = "needs_reauth" if error_code == "ITEM_LOGIN_REQUIRED" else "error"
            db.commit()
            return {"status": "health_updated", "health": bank.health}
        if webhook_code in _NEEDS_REAUTH_CODES:
            bank.health = "needs_reauth"
            db.commit()
            return {"status": "health_updated", "health": bank.health}
        if webhook_code == "LOGIN_REPAIRED":
            bank.health = "healthy"
            db.commit()
            return {"status": "health_updated", "health": bank.health}

    return {"status": "ignored", "reason": "unhandled webhook_type/code"}
