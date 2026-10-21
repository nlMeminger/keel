"""Cross-cutting behavior of app.dependencies.get_current_user's API-token fallback
(API_SPEC.md §18, ROADMAP 8.5) — exercised against a real resource route (accounts)
rather than a throwaway one, so the test proves the actual production dependency chain."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

from app.admin.models import ApiToken
from app.auth.models import User


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _promote_to_admin(db: OrmSession, user_id: uuid.UUID) -> None:
    user = db.get(User, user_id)
    assert user is not None
    user.role = "admin"
    db.commit()


def _issue_token(
    client: TestClient,
    admin_token: str,
    bound_user_id: uuid.UUID,
    scopes: list[str],
    expires_at: datetime | None = None,
) -> str:
    body: dict[str, object] = {
        "user_id": str(bound_user_id),
        "label": "test token",
        "scopes": scopes,
    }
    if expires_at is not None:
        body["expires_at"] = expires_at.isoformat()
    resp = client.post("/api/v1/admin/api-tokens", json=body, headers=_auth_headers(admin_token))
    assert resp.status_code == 201
    secret: str = resp.json()["data"]["secret"]
    return secret


def test_read_only_token_authenticates_a_read_request_scoped_to_its_bound_user(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, admin_id = register_and_login("token-admin-a@example.com")
    _promote_to_admin(db, admin_id)
    _, bound_user_id = register_and_login("token-bound-a@example.com")

    secret = _issue_token(client, admin_token, bound_user_id, ["read"])

    resp = client.get("/api/v1/accounts", headers=_auth_headers(secret))
    assert resp.status_code == 200


def test_read_only_token_cannot_write(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, admin_id = register_and_login("token-admin-b@example.com")
    _promote_to_admin(db, admin_id)
    _, bound_user_id = register_and_login("token-bound-b@example.com")

    secret = _issue_token(client, admin_token, bound_user_id, ["read"])

    resp = client.post(
        "/api/v1/accounts",
        json={"name": "Checking", "account_type": "checking", "balance": "0", "detail": {}},
        headers=_auth_headers(secret),
    )
    assert resp.status_code == 403


def test_read_write_token_can_write_and_it_acts_as_the_bound_user(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, admin_id = register_and_login("token-admin-c@example.com")
    _promote_to_admin(db, admin_id)
    _, bound_user_id = register_and_login("token-bound-c@example.com")

    secret = _issue_token(client, admin_token, bound_user_id, ["read", "write"])

    create_resp = client.post(
        "/api/v1/accounts",
        json={"name": "Checking", "account_type": "checking", "balance": "0", "detail": {}},
        headers=_auth_headers(secret),
    )
    assert create_resp.status_code == 201

    list_resp = client.get("/api/v1/accounts", headers=_auth_headers(secret))
    names = [row["name"] for row in list_resp.json()["data"]]
    assert "Checking" in names


def test_token_never_grants_admin_access_regardless_of_who_issued_it(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, admin_id = register_and_login("token-admin-d@example.com")
    _promote_to_admin(db, admin_id)
    _, bound_user_id = register_and_login("token-bound-d@example.com")

    secret = _issue_token(client, admin_token, bound_user_id, ["read", "write"])

    resp = client.get("/api/v1/admin/users", headers=_auth_headers(secret))
    assert resp.status_code == 403


def test_revoked_token_gets_401_on_next_use(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, admin_id = register_and_login("token-admin-e@example.com")
    _promote_to_admin(db, admin_id)
    _, bound_user_id = register_and_login("token-bound-e@example.com")

    create_resp = client.post(
        "/api/v1/admin/api-tokens",
        json={"user_id": str(bound_user_id), "label": "revoke-me", "scopes": ["read"]},
        headers=_auth_headers(admin_token),
    )
    data = create_resp.json()["data"]
    secret = data["secret"]
    token_id = data["token"]["id"]

    assert client.get("/api/v1/accounts", headers=_auth_headers(secret)).status_code == 200

    revoke_resp = client.delete(
        f"/api/v1/admin/api-tokens/{token_id}", headers=_auth_headers(admin_token)
    )
    assert revoke_resp.status_code == 204

    resp = client.get("/api/v1/accounts", headers=_auth_headers(secret))
    assert resp.status_code == 401


def test_expired_token_gets_401(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, admin_id = register_and_login("token-admin-f@example.com")
    _promote_to_admin(db, admin_id)
    _, bound_user_id = register_and_login("token-bound-f@example.com")

    secret = _issue_token(
        client,
        admin_token,
        bound_user_id,
        ["read"],
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )

    resp = client.get("/api/v1/accounts", headers=_auth_headers(secret))
    assert resp.status_code == 401


def test_token_updates_last_used_at(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, admin_id = register_and_login("token-admin-g@example.com")
    _promote_to_admin(db, admin_id)
    _, bound_user_id = register_and_login("token-bound-g@example.com")

    create_resp = client.post(
        "/api/v1/admin/api-tokens",
        json={"user_id": str(bound_user_id), "label": "last-used", "scopes": ["read"]},
        headers=_auth_headers(admin_token),
    )
    token_id = uuid.UUID(create_resp.json()["data"]["token"]["id"])
    secret = create_resp.json()["data"]["secret"]

    client.get("/api/v1/accounts", headers=_auth_headers(secret))

    db.expire_all()
    row = db.get(ApiToken, token_id)
    assert row is not None
    assert row.last_used_at is not None
