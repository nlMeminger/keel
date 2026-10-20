import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from app.jobs.models import Job
from app.jobs.service import create_job, run_job
from conftest import TestSessionLocal


def test_poll_pending_then_running_then_terminal_exactly_once(
    client: TestClient, db: DbSession, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, user_id = register_and_login("poller@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    job = create_job(db, "bulk_import", owner_id=user_id)

    pending_resp = client.get(f"/api/v1/sync/jobs/{job.id}", headers=headers)
    assert pending_resp.status_code == 200
    assert pending_resp.json()["data"]["status"] == "pending"

    def report_progress() -> dict[str, int]:
        job.progress_current = 5
        job.progress_total = 10
        db.commit()
        return {"imported": 5}

    run_job(job.id, report_progress, session_factory=TestSessionLocal)

    terminal_resp = client.get(f"/api/v1/sync/jobs/{job.id}", headers=headers)
    assert terminal_resp.status_code == 200
    terminal_data = terminal_resp.json()["data"]
    assert terminal_data["status"] == "succeeded"
    assert terminal_data["progress"] == {"current": 5, "total": 10}
    assert terminal_data["started_at"] is not None
    assert terminal_data["finished_at"] is not None

    # Polling again returns the same terminal status — never flaps back to "running".
    second_poll = client.get(f"/api/v1/sync/jobs/{job.id}", headers=headers)
    assert second_poll.json()["data"]["status"] == "succeeded"


def test_failed_job_reports_terminal_status_and_error(
    client: TestClient, db: DbSession, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, user_id = register_and_login("failer@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    job = create_job(db, "transaction_sync", owner_id=user_id)

    def boom() -> None:
        raise RuntimeError("sync blew up")

    try:
        run_job(job.id, boom, session_factory=TestSessionLocal)
    except RuntimeError:
        pass

    resp = client.get(f"/api/v1/sync/jobs/{job.id}", headers=headers)
    data = resp.json()["data"]
    assert data["status"] == "failed"
    assert data["error"] == "sync blew up"


def test_a_second_users_token_cannot_see_the_first_users_job(
    client: TestClient,
    db: DbSession,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
) -> None:
    _owner_token, owner_id = register_and_login("job-owner@example.com")
    job = create_job(db, "bulk_import", owner_id=owner_id)

    intruder_token, _intruder_id = register_and_login("job-intruder@example.com")
    resp = client.get(
        f"/api/v1/sync/jobs/{job.id}", headers={"Authorization": f"Bearer {intruder_token}"}
    )
    assert resp.status_code == 404


def test_nonexistent_job_returns_404(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("nobody@example.com")
    resp = client.get(
        f"/api/v1/sync/jobs/{uuid.uuid4()}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404


def test_job_requires_auth(db: DbSession, client: TestClient) -> None:
    job = Job(type="bulk_import", owner_id=None)
    db.add(job)
    db.commit()
    resp = client.get(f"/api/v1/sync/jobs/{job.id}")
    assert resp.status_code == 401
