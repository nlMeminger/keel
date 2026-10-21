import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

from app.auth.models import User


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _promote_to_admin(db: OrmSession, user_id: uuid.UUID) -> None:
    user = db.get(User, user_id)
    assert user is not None
    user.role = "admin"
    db.commit()


def test_admin_routes_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/admin/users").status_code == 401


def test_non_admin_gets_403_on_admin_route(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("plain-user@example.com")
    resp = client.get("/api/v1/admin/users", headers=_auth_headers(token))
    assert resp.status_code == 403


def test_admin_succeeds_on_admin_route(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    token, user_id = register_and_login("admin-user@example.com")
    _promote_to_admin(db, user_id)
    resp = client.get("/api/v1/admin/users", headers=_auth_headers(token))
    assert resp.status_code == 200


def test_admin_check_is_distinct_from_ownership(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    """A non-owner admin reaches another user's metadata (role=admin is sufficient on its
    own); a non-owner non-admin is rejected regardless of whose id it names — proving the
    admin dependency is a role check, not the ownership check every other write route uses."""
    admin_token, admin_id = register_and_login("admin-two@example.com")
    _promote_to_admin(db, admin_id)
    _other_token, other_id = register_and_login("someone-else@example.com")

    as_admin = client.get(f"/api/v1/admin/users/{other_id}", headers=_auth_headers(admin_token))
    assert as_admin.status_code == 200
    assert as_admin.json()["data"]["id"] == str(other_id)

    non_admin_token, _ = register_and_login("plain-user-two@example.com")
    as_non_admin = client.get(
        f"/api/v1/admin/users/{other_id}", headers=_auth_headers(non_admin_token)
    )
    assert as_non_admin.status_code == 403
