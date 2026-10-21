import app.database as database
from app.banks import service
from app.celery_app import celery_app
from app.jobs.service import create_job, run_job


@celery_app.task(name="banks.reconcile_removed_plaid_items")
def reconcile_removed_plaid_items_task() -> None:
    """Celery beat's scheduled ghost-item sweep (ROADMAP 7.11) — system-wide, same
    create-a-visible-Job precedent as app.sync.tasks's scheduled_sync_*_task functions,
    even though (like those) no one polls it directly."""
    db = database.SessionLocal()
    try:
        job = create_job(db, "plaid_item_reconciliation", owner_id=None)
    finally:
        db.close()

    def _run() -> dict[str, int]:
        db = database.SessionLocal()
        try:
            return service.reconcile_removed_plaid_items(db)
        finally:
            db.close()

    run_job(job.id, _run, session_factory=database.SessionLocal)
