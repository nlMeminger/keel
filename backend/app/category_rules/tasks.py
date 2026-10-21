import uuid

import app.database as database
from app.category_rules import service
from app.celery_app import celery_app
from app.jobs.service import run_job


@celery_app.task(name="category_rules.apply")
def apply_category_rules_task(job_id: str, user_id: str) -> None:
    """Celery body for the `category_rule_apply` job (API_SPEC.md §7) — runs through the
    generic job-runner wrapper so status/result/error tracking is identical to every other
    job type, rather than reinventing it here.

    Resolves `database.SessionLocal` via module attribute (not a plain `from...import`) so
    tests — which run this synchronously in-process under Celery's eager mode and patch that
    attribute to point at the test database — route to the right database without a real
    worker process ever being involved.
    """

    def _run() -> dict[str, int]:
        db = database.SessionLocal()
        try:
            return service.apply_active_rules(db, uuid.UUID(user_id))
        finally:
            db.close()

    run_job(uuid.UUID(job_id), _run, session_factory=database.SessionLocal)
