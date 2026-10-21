"""ROADMAP 8.6's own success criterion: every write across 8.2-8.5's surface produces a
matching AdminAuditLog row, verified by asserting the count — not just a 200 from each
endpoint. One test exercises every admin write route once and checks the resulting table."""

import uuid
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession

from app.admin.models import AdminAuditLog
from app.auth.models import User
from app.banks import service as banks_service
from app.banks.models import Bank, PlaidItem
from app.core.encryption import encrypt


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


class _FakeClient:
    def item_get(self, request: object) -> object:
        class _Item:
            error = None

        class _Response:
            item = _Item()

        return _Response()


def test_audit_log_requires_admin(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _ = register_and_login("plain-audit@example.com")
    assert client.get("/api/v1/admin/audit-log", headers=_auth_headers(token)).status_code == 403


def test_every_admin_write_route_produces_exactly_one_audit_log_row(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin_token, admin_id = _make_admin(client, register_and_login, db, "audit-admin@example.com")
    headers = _auth_headers(admin_token)

    # 1. user.create
    create_resp = client.post(
        "/api/v1/admin/users",
        json={"email": "audit-created@example.com", "name": "Created", "role": "user"},
        headers=headers,
    )
    assert create_resp.status_code == 201
    created_user_id = create_resp.json()["data"]["user"]["id"]

    # 2. user.update
    assert (
        client.patch(
            f"/api/v1/admin/users/{created_user_id}", json={"name": "Renamed"}, headers=headers
        ).status_code
        == 200
    )

    # 3. user.reset_password
    assert (
        client.post(
            f"/api/v1/admin/users/{created_user_id}/reset-password", json={}, headers=headers
        ).status_code
        == 200
    )

    # 4. user.revoke_sessions
    assert (
        client.post(
            f"/api/v1/admin/users/{created_user_id}/revoke-sessions", headers=headers
        ).status_code
        == 204
    )

    # 5. user.update_plaid_access
    assert (
        client.patch(
            f"/api/v1/admin/users/{created_user_id}/plaid-access",
            json={"enabled": False, "monthly_call_limit": None},
            headers=headers,
        ).status_code
        == 200
    )

    # 6. user.delete (a separate throwaway user, so the subsequent calls above stay valid)
    _, delete_target_id = register_and_login("audit-delete-target@example.com")
    assert (
        client.request(
            "DELETE",
            f"/api/v1/admin/users/{delete_target_id}",
            json={"confirm": True},
            headers=headers,
        ).status_code
        == 204
    )

    # 7. sync.trigger_all_transactions
    assert client.post("/api/v1/admin/sync/transactions", headers=headers).status_code == 202

    # 8. sync.trigger_all_balances
    assert client.post("/api/v1/admin/sync/balances", headers=headers).status_code == 202

    # 9. bank.health_check
    _, bank_owner_id = register_and_login("audit-bank-owner@example.com")
    bank = _make_bank(db, bank_owner_id)
    monkeypatch.setattr(banks_service, "get_plaid_client", lambda: _FakeClient())
    assert (
        client.post(f"/api/v1/admin/banks/{bank.id}/health-check", headers=headers).status_code
        == 200
    )

    # 10. plaid.reconcile_items
    assert client.post("/api/v1/admin/plaid/reconcile-items", headers=headers).status_code == 202

    # 11. api_token.create
    _, token_bound_user_id = register_and_login("audit-token-bound@example.com")
    token_resp = client.post(
        "/api/v1/admin/api-tokens",
        json={"user_id": str(token_bound_user_id), "label": "audit", "scopes": ["read"]},
        headers=headers,
    )
    assert token_resp.status_code == 201
    api_token_id = token_resp.json()["data"]["token"]["id"]

    # 12. api_token.update
    assert (
        client.patch(
            f"/api/v1/admin/api-tokens/{api_token_id}",
            json={"label": "renamed"},
            headers=headers,
        ).status_code
        == 200
    )

    # 13. api_token.revoke
    assert (
        client.delete(f"/api/v1/admin/api-tokens/{api_token_id}", headers=headers).status_code
        == 204
    )

    total = db.scalar(select(func.count()).select_from(AdminAuditLog))
    assert total == 13

    actions = set(db.scalars(select(AdminAuditLog.action)).all())
    assert actions == {
        "user.create",
        "user.update",
        "user.reset_password",
        "user.revoke_sessions",
        "user.update_plaid_access",
        "user.delete",
        "sync.trigger_all_transactions",
        "sync.trigger_all_balances",
        "bank.health_check",
        "plaid.reconcile_items",
        "api_token.create",
        "api_token.update",
        "api_token.revoke",
    }
    assert all(row.admin_user_id == admin_id for row in db.scalars(select(AdminAuditLog)).all())


def test_audit_log_filters_by_action(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, admin_id = _make_admin(client, register_and_login, db, "audit-filter@example.com")
    client.post(
        "/api/v1/admin/users",
        json={"email": "audit-filter-target@example.com", "name": "X", "role": "user"},
        headers=_auth_headers(admin_token),
    )

    resp = client.get(
        "/api/v1/admin/audit-log",
        params={"action": "user.create"},
        headers=_auth_headers(admin_token),
    )
    assert resp.status_code == 200
    rows = resp.json()["data"]
    assert len(rows) == 1
    assert rows[0]["action"] == "user.create"
    assert rows[0]["admin_user_id"] == str(admin_id)
