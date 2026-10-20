import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session as DbSession

from app.database import SessionLocal
from app.jobs.models import Job


def create_job(db: DbSession, job_type: str, owner_id: uuid.UUID | None) -> Job:
    job = Job(type=job_type, owner_id=owner_id)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def run_job(
    job_id: uuid.UUID,
    func: Callable[[], dict[str, Any] | None],
    session_factory: Callable[[], DbSession] = SessionLocal,
) -> None:
    """Generic wrapper every job-backed Celery task body runs through.

    Marks the Job row running -> succeeded/failed and always records the outcome before
    re-raising on failure — a crashed task must never leave a Job stuck in "running" or
    silently lose the error (session_factory is injectable so tests can point it at a
    different database without touching real Celery infra).
    """
    db = session_factory()
    try:
        job = db.get(Job, job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found")

        job.status = "running"
        job.started_at = datetime.now(UTC)
        db.commit()

        try:
            result = func()
        except Exception as exc:
            job.status = "failed"
            job.finished_at = datetime.now(UTC)
            job.error = str(exc)
            db.commit()
            raise

        job.status = "succeeded"
        job.finished_at = datetime.now(UTC)
        job.result = result
        db.commit()
    finally:
        db.close()
