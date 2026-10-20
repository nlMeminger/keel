import pytest
from sqlalchemy.orm import Session as DbSession

from app.jobs.service import create_job, run_job
from conftest import TestSessionLocal


def test_run_job_marks_succeeded_with_result(db: DbSession) -> None:
    job = create_job(db, "bulk_import", owner_id=None)

    run_job(job.id, lambda: {"count": 3}, session_factory=TestSessionLocal)

    db.refresh(job)
    assert job.status == "succeeded"
    assert job.result == {"count": 3}
    assert job.started_at is not None
    assert job.finished_at is not None
    assert job.error is None


def test_run_job_marks_failed_with_error_and_reraises(db: DbSession) -> None:
    job = create_job(db, "bulk_import", owner_id=None)

    def boom() -> None:
        raise RuntimeError("deliberate failure")

    with pytest.raises(RuntimeError, match="deliberate failure"):
        run_job(job.id, boom, session_factory=TestSessionLocal)

    db.refresh(job)
    assert job.status == "failed"
    assert job.error == "deliberate failure"
    assert job.started_at is not None
    assert job.finished_at is not None
