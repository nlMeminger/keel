import uuid

import app.database as database
from app.banks import service
from app.celery_app import celery_app
from app.jobs.models import Job
from app.jobs.service import create_job, run_job


@celery_app.task(name="banks.reconcile_removed_plaid_items")
def reconcile_removed_plaid_items_task(job_id: str | None = None) -> None:
    """Celery beat's scheduled ghost-item sweep (ROADMAP 7.11) calls this with no `job_id`
    and it creates its own system Job (owner_id=None); an admin's manual
    `POST /admin/plaid/reconcile-items` (API_SPEC.md §18) creates the Job itself first and
    passes the id, so both paths share one task body."""
    db = database.SessionLocal()
    try:
        if job_id is not None:
            job = db.get(Job, uuid.UUID(job_id))
            assert job is not None
        else:
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
