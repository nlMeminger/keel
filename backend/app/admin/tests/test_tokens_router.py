import uuid
from collections.abc import Callable

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


def _make_admin(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
    email: str,
) -> tuple[str, uuid.UUID]:
    token, user_id = register_and_login(email)
    _promote_to_admin(db, user_id)
    return token, user_id


def test_tokens_routes_require_admin(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _ = register_and_login("plain-tokens@example.com")
    assert client.get("/api/v1/admin/api-tokens", headers=_auth_headers(token)).status_code == 403
    assert client.post("/api/v1/admin/api-tokens", headers=_auth_headers(token)).status_code == 403


def test_create_token_returns_secret_once_and_never_again(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, _ = _make_admin(client, register_and_login, db, "admin-tok@example.com")
    _, bound_user_id = register_and_login("token-bound-user@example.com")

    resp = client.post(
        "/api/v1/admin/api-tokens",
        json={"user_id": str(bound_user_id), "label": "integration", "scopes": ["read"]},
        headers=_auth_headers(admin_token),
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    secret = data["secret"]
    assert len(secret) >= 20

    list_resp = client.get("/api/v1/admin/api-tokens", headers=_auth_headers(admin_token))
    assert list_resp.status_code == 200
    for row in list_resp.json()["data"]:
        assert "secret" not in row
        assert "token_hash" not in row


def test_create_token_rejects_write_only_scope(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, _ = _make_admin(client, register_and_login, db, "admin-tok-2@example.com")
    _, bound_user_id = register_and_login("token-bound-user-2@example.com")

    resp = client.post(
        "/api/v1/admin/api-tokens",
        json={"user_id": str(bound_user_id), "label": "bad", "scopes": ["write"]},
        headers=_auth_headers(admin_token),
    )
    assert resp.status_code == 422


def test_update_token_renames_label_without_rotating_secret(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, _ = _make_admin(client, register_and_login, db, "admin-tok-3@example.com")
    _, bound_user_id = register_and_login("token-bound-user-3@example.com")
    create_resp = client.post(
        "/api/v1/admin/api-tokens",
        json={"user_id": str(bound_user_id), "label": "old-label", "scopes": ["read"]},
        headers=_auth_headers(admin_token),
    )
    token_id = create_resp.json()["data"]["token"]["id"]

    resp = client.patch(
        f"/api/v1/admin/api-tokens/{token_id}",
        json={"label": "new-label"},
        headers=_auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["label"] == "new-label"


def test_revoke_token(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, _ = _make_admin(client, register_and_login, db, "admin-tok-4@example.com")
    _, bound_user_id = register_and_login("token-bound-user-4@example.com")
    create_resp = client.post(
        "/api/v1/admin/api-tokens",
        json={"user_id": str(bound_user_id), "label": "to-revoke", "scopes": ["read"]},
        headers=_auth_headers(admin_token),
    )
    token_id = create_resp.json()["data"]["token"]["id"]

    resp = client.delete(f"/api/v1/admin/api-tokens/{token_id}", headers=_auth_headers(admin_token))
    assert resp.status_code == 204
    db.expire_all()
    row = db.get(ApiToken, uuid.UUID(token_id))
    assert row is not None
    assert row.revoked_at is not None
