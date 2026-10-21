import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

from app.auth.models import User
from app.banks.models import PlaidAPICall


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


def test_plaid_stats_routes_require_admin(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _ = register_and_login("plain-stats@example.com")
    resp = client.get(
        "/api/v1/admin/plaid/api-stats",
        params={"group_by": "user"},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 403
    assert client.get("/api/v1/admin/plaid/calls", headers=_auth_headers(token)).status_code == 403


def test_api_stats_group_by_user_returns_distinct_sums_not_a_combined_total(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, _ = _make_admin(client, register_and_login, db, "admin-stats@example.com")
    _, user_a = register_and_login("stats-user-a@example.com")
    _, user_b = register_and_login("stats-user-b@example.com")
    for _ in range(3):
        db.add(PlaidAPICall(user_id=user_a, endpoint="accounts_get", status="success"))
    for _ in range(5):
        db.add(PlaidAPICall(user_id=user_b, endpoint="accounts_get", status="success"))
    db.commit()

    resp = client.get(
        "/api/v1/admin/plaid/api-stats",
        params={"group_by": "user"},
        headers=_auth_headers(admin_token),
    )
    assert resp.status_code == 200
    counts = {row["group"]: row["count"] for row in resp.json()["data"]}
    assert counts[str(user_a)] == 3
    assert counts[str(user_b)] == 5


def test_api_stats_group_by_endpoint(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, _ = _make_admin(client, register_and_login, db, "admin-stats-2@example.com")
    _, user_a = register_and_login("stats-user-c@example.com")
    db.add(PlaidAPICall(user_id=user_a, endpoint="accounts_get", status="success"))
    db.add(PlaidAPICall(user_id=user_a, endpoint="accounts_get", status="success"))
    db.add(PlaidAPICall(user_id=user_a, endpoint="transactions_sync", status="success"))
    db.commit()

    resp = client.get(
        "/api/v1/admin/plaid/api-stats",
        params={"group_by": "endpoint"},
        headers=_auth_headers(admin_token),
    )
    assert resp.status_code == 200
    counts = {row["group"]: row["count"] for row in resp.json()["data"]}
    assert counts["accounts_get"] == 2
    assert counts["transactions_sync"] == 1


def test_api_stats_rejects_invalid_group_by(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, _ = _make_admin(client, register_and_login, db, "admin-stats-3@example.com")
    resp = client.get(
        "/api/v1/admin/plaid/api-stats",
        params={"group_by": "not-a-real-option"},
        headers=_auth_headers(admin_token),
    )
    assert resp.status_code == 422


def test_list_calls_filters_by_user_and_status(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, _ = _make_admin(client, register_and_login, db, "admin-calls@example.com")
    _, user_a = register_and_login("calls-user-a@example.com")
    _, user_b = register_and_login("calls-user-b@example.com")
    db.add(PlaidAPICall(user_id=user_a, endpoint="accounts_get", status="success"))
    db.add(PlaidAPICall(user_id=user_a, endpoint="item_get", status="error", error_code="X"))
    db.add(PlaidAPICall(user_id=user_b, endpoint="accounts_get", status="success"))
    db.commit()

    resp = client.get(
        "/api/v1/admin/plaid/calls",
        params={"user_id": str(user_a), "status": "error"},
        headers=_auth_headers(admin_token),
    )
    assert resp.status_code == 200
    rows = resp.json()["data"]
    assert len(rows) == 1
    assert rows[0]["user_id"] == str(user_a)
    assert rows[0]["status"] == "error"
    assert rows[0]["error_code"] == "X"
