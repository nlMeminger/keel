import logging
import uuid
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

from app.admin.models import LogEntry
from app.admin.service import list_logs_stmt
from app.auth.models import User
from app.banks import service as banks_service
from app.banks.models import Bank, PlaidItem
from app.core.encryption import encrypt
from app.jobs.models import Job


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _promote_to_admin(db: OrmSession, user_id: uuid.UUID) -> None:
    user = db.get(User, user_id)
    assert user is not None
    user.role = "admin"
    db.commit()


def _make_admin(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
    email: str,
) -> tuple[str, uuid.UUID]:
    token, user_id = register_and_login(email)
    _promote_to_admin(db, user_id)
    return token, user_id


def _make_bank(db: OrmSession, owner_id: uuid.UUID) -> Bank:
    item = PlaidItem(
        access_token=encrypt("fake-access-token"),
        item_id=f"item-{uuid.uuid4()}",
        institution_id="ins_1",
        institution_name="Sandbox Bank",
    )
    db.add(item)
    db.flush()
    bank = Bank(owner_id=owner_id, plaid_item_id=item.id)
    db.add(bank)
    db.commit()
    db.refresh(bank)
    return bank


class _FakeError:
    def __init__(self, error_code: str) -> None:
        self.error_code = error_code


class _FakeItem:
    def __init__(self, error: _FakeError | None) -> None:
        self.error = error


class _FakeItemGetResponse:
    def __init__(self, error: _FakeError | None) -> None:
        self.item = _FakeItem(error)


class _FakeClient:
    def __init__(self, error: _FakeError | None) -> None:
        self._error = error

    def item_get(self, request: object) -> _FakeItemGetResponse:
        return _FakeItemGetResponse(self._error)


def test_operations_routes_require_admin(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _ = register_and_login("plain-ops@example.com")
    assert client.get("/api/v1/admin/jobs", headers=_auth_headers(token)).status_code == 403
    assert client.get("/api/v1/admin/logs", headers=_auth_headers(token)).status_code == 403
    assert (
        client.post("/api/v1/admin/sync/transactions", headers=_auth_headers(token)).status_code
        == 403
    )
    assert client.get("/api/v1/admin/config", headers=_auth_headers(token)).status_code == 403


def test_list_jobs_shows_jobs_across_every_user(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, _ = _make_admin(client, register_and_login, db, "admin-jobs@example.com")
    _, user_a = register_and_login("jobs-user-a@example.com")
    _, user_b = register_and_login("jobs-user-b@example.com")
    db.add(Job(type="transaction_sync", owner_id=user_a))
    db.add(Job(type="balance_sync", owner_id=user_b))
    db.commit()

    resp = client.get("/api/v1/admin/jobs", headers=_auth_headers(admin_token))
    assert resp.status_code == 200
    owner_ids = {row["owner_id"] for row in resp.json()["data"]}
    assert str(user_a) in owner_ids
    assert str(user_b) in owner_ids


def test_list_jobs_filters_by_status_and_type(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, _ = _make_admin(client, register_and_login, db, "admin-jobs-2@example.com")
    _, user_a = register_and_login("jobs-user-c@example.com")
    db.add(Job(type="transaction_sync", owner_id=user_a, status="succeeded"))
    db.add(Job(type="balance_sync", owner_id=user_a, status="failed"))
    db.commit()

    resp = client.get(
        "/api/v1/admin/jobs",
        params={"type": "transaction_sync", "status": "succeeded"},
        headers=_auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert all(row["type"] == "transaction_sync" for row in resp.json()["data"])
    assert all(row["status"] == "succeeded" for row in resp.json()["data"])


def test_logs_are_captured_and_secret_like_text_is_masked(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    """The DatabaseLogHandler is installed once, globally, at app.main import time
    (conftest's `from app.main import app`) — no handler needs attaching here."""
    admin_token, _ = _make_admin(client, register_and_login, db, "admin-logs@example.com")

    fake_secret = "a" * 40
    logging.getLogger("app.test_operations").error("token leaked: %s", fake_secret)

    resp = client.get("/api/v1/admin/logs", headers=_auth_headers(admin_token))
    assert resp.status_code == 200
    messages = [row["message"] for row in resp.json()["data"]]
    assert any("token leaked" in m for m in messages)
    assert not any(fake_secret in m for m in messages)
    assert any(m.endswith(fake_secret[-4:]) for m in messages)


def test_logs_filter_by_level(db: OrmSession) -> None:
    db.add(LogEntry(level="WARNING", logger_name="app.x", message="a warning"))
    db.add(LogEntry(level="ERROR", logger_name="app.x", message="an error"))
    db.commit()

    rows = db.scalars(list_logs_stmt("ERROR", None, None)).all()
    assert [r.message for r in rows] == ["an error"]


def test_sync_all_transactions_triggers_a_pollable_job(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, _ = _make_admin(client, register_and_login, db, "admin-sync-all@example.com")
    resp = client.post("/api/v1/admin/sync/transactions", headers=_auth_headers(admin_token))
    assert resp.status_code == 202
    job_id = resp.json()["data"]["job_id"]
    job = db.get(Job, uuid.UUID(job_id))
    assert job is not None
    assert job.type == "transaction_sync"
    assert job.owner_id is None


def test_sync_all_balances_triggers_a_pollable_job(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, _ = _make_admin(client, register_and_login, db, "admin-sync-all-2@example.com")
    resp = client.post("/api/v1/admin/sync/balances", headers=_auth_headers(admin_token))
    assert resp.status_code == 202
    job = db.get(Job, uuid.UUID(resp.json()["data"]["job_id"]))
    assert job is not None
    assert job.type == "balance_sync"


def test_reconcile_items_triggers_a_pollable_job(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, _ = _make_admin(client, register_and_login, db, "admin-reconcile@example.com")
    resp = client.post("/api/v1/admin/plaid/reconcile-items", headers=_auth_headers(admin_token))
    assert resp.status_code == 202
    job = db.get(Job, uuid.UUID(resp.json()["data"]["job_id"]))
    assert job is not None
    assert job.type == "plaid_item_reconciliation"


def test_health_check_updates_any_users_bank_health(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin_token, _ = _make_admin(client, register_and_login, db, "admin-health@example.com")
    _, owner_id = register_and_login("health-check-owner@example.com")
    bank = _make_bank(db, owner_id)

    monkeypatch.setattr(
        banks_service,
        "get_plaid_client",
        lambda: _FakeClient(_FakeError("ITEM_LOGIN_REQUIRED")),
    )
    resp = client.post(
        f"/api/v1/admin/banks/{bank.id}/health-check", headers=_auth_headers(admin_token)
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["health"] == "needs_reauth"
    db.refresh(bank)
    assert bank.health == "needs_reauth"


def test_health_check_does_not_require_plaid_enabled(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin_token, _ = _make_admin(client, register_and_login, db, "admin-health-2@example.com")
    _, owner_id = register_and_login("health-check-owner-2@example.com")
    owner = db.get(User, owner_id)
    assert owner is not None
    owner.plaid_enabled = False
    db.commit()
    bank = _make_bank(db, owner_id)

    monkeypatch.setattr(banks_service, "get_plaid_client", lambda: _FakeClient(None))
    resp = client.post(
        f"/api/v1/admin/banks/{bank.id}/health-check", headers=_auth_headers(admin_token)
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["health"] == "healthy"


def test_get_config_never_includes_secrets(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, _ = _make_admin(client, register_and_login, db, "admin-config@example.com")
    resp = client.get("/api/v1/admin/config", headers=_auth_headers(admin_token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert set(data.keys()) == {"environment", "cors_origins", "beat_schedule"}
