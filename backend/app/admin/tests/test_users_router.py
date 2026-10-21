import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.auth.models import Session, User
from app.auth.service import create_session
from app.banks.models import Bank, PlaidItem


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _promote_to_admin(db: OrmSession, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    assert user is not None
    user.role = "admin"
    db.commit()
    db.refresh(user)
    return user


def _make_admin(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
    email: str,
) -> tuple[str, uuid.UUID]:
    token, user_id = register_and_login(email)
    _promote_to_admin(db, user_id)
    return token, user_id


def test_list_users_filters_by_role_and_status(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, _ = _make_admin(client, register_and_login, db, "admin-list@example.com")
    _, suspended_id = register_and_login("suspended-list@example.com")
    suspended = db.get(User, suspended_id)
    assert suspended is not None
    suspended.status = "suspended"
    db.commit()

    resp = client.get(
        "/api/v1/admin/users", params={"status": "suspended"}, headers=_auth_headers(admin_token)
    )
    assert resp.status_code == 200
    ids = {row["id"] for row in resp.json()["data"]}
    assert str(suspended_id) in ids

    resp = client.get(
        "/api/v1/admin/users", params={"role": "admin"}, headers=_auth_headers(admin_token)
    )
    assert all(row["role"] == "admin" for row in resp.json()["data"])


def test_create_user_with_explicit_password(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, _ = _make_admin(client, register_and_login, db, "admin-create@example.com")
    resp = client.post(
        "/api/v1/admin/users",
        json={
            "email": "provisioned@example.com",
            "name": "Provisioned",
            "role": "user",
            "password": "a-real-password",
        },
        headers=_auth_headers(admin_token),
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["initial_password"] == "a-real-password"
    assert data["user"]["must_change_password"] is True


def test_create_user_without_password_autogenerates_one(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, _ = _make_admin(client, register_and_login, db, "admin-create-2@example.com")
    resp = client.post(
        "/api/v1/admin/users",
        json={"email": "autogen@example.com", "name": "Autogen", "role": "user"},
        headers=_auth_headers(admin_token),
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert len(data["initial_password"]) >= 20


def test_create_user_rejects_duplicate_email(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, _ = _make_admin(client, register_and_login, db, "admin-dup@example.com")
    resp = client.post(
        "/api/v1/admin/users",
        json={"email": "admin-dup@example.com", "name": "Dup", "role": "user"},
        headers=_auth_headers(admin_token),
    )
    assert resp.status_code == 409


def test_update_user_rejects_demoting_last_admin(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, admin_id = _make_admin(client, register_and_login, db, "only-admin@example.com")
    resp = client.patch(
        f"/api/v1/admin/users/{admin_id}",
        json={"role": "user"},
        headers=_auth_headers(admin_token),
    )
    assert resp.status_code == 409


def test_update_user_rejects_suspending_last_admin(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, admin_id = _make_admin(
        client, register_and_login, db, "only-admin-suspend@example.com"
    )
    resp = client.patch(
        f"/api/v1/admin/users/{admin_id}",
        json={"status": "suspended"},
        headers=_auth_headers(admin_token),
    )
    assert resp.status_code == 409


def test_update_user_allows_demoting_when_another_admin_remains(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, _ = _make_admin(client, register_and_login, db, "admin-a@example.com")
    _, second_admin_id = _make_admin(client, register_and_login, db, "admin-b@example.com")

    resp = client.patch(
        f"/api/v1/admin/users/{second_admin_id}",
        json={"role": "user"},
        headers=_auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["role"] == "user"


def test_reset_password_autogenerates_and_revokes_sessions(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, _ = _make_admin(client, register_and_login, db, "admin-reset@example.com")
    _, target_id = register_and_login("reset-target@example.com")
    target = db.get(User, target_id)
    assert target is not None
    create_session(db, target, user_agent=None, ip_address=None)

    resp = client.post(
        f"/api/v1/admin/users/{target_id}/reset-password",
        json={},
        headers=_auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]["temporary_password"]) >= 20

    db.expire_all()
    refreshed = db.get(User, target_id)
    assert refreshed is not None
    assert refreshed.must_change_password is True
    active_sessions = db.scalars(
        select(Session).where(Session.user_id == target_id, Session.revoked_at.is_(None))
    ).all()
    assert active_sessions == []


def test_reset_password_with_explicit_value_does_not_echo_it_back(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, _ = _make_admin(client, register_and_login, db, "admin-reset-2@example.com")
    _, target_id = register_and_login("reset-target-2@example.com")

    resp = client.post(
        f"/api/v1/admin/users/{target_id}/reset-password",
        json={"password": "admin-chosen-password"},
        headers=_auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["temporary_password"] is None


def test_plaid_access_update(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, _ = _make_admin(client, register_and_login, db, "admin-plaid@example.com")
    _, target_id = register_and_login("plaid-target@example.com")

    resp = client.patch(
        f"/api/v1/admin/users/{target_id}/plaid-access",
        json={"enabled": False, "monthly_call_limit": 100},
        headers=_auth_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["plaid_enabled"] is False
    assert data["plaid_monthly_call_limit"] == 100


def test_delete_user_requires_confirm(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, _ = _make_admin(client, register_and_login, db, "admin-delete@example.com")
    _, target_id = register_and_login("delete-target@example.com")

    resp = client.request(
        "DELETE",
        f"/api/v1/admin/users/{target_id}",
        json={"confirm": False},
        headers=_auth_headers(admin_token),
    )
    assert resp.status_code == 400


def test_delete_user_rejects_last_admin(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, admin_id = _make_admin(
        client, register_and_login, db, "only-admin-delete@example.com"
    )
    resp = client.request(
        "DELETE",
        f"/api/v1/admin/users/{admin_id}",
        json={"confirm": True},
        headers=_auth_headers(admin_token),
    )
    assert resp.status_code == 409


def test_delete_user_removes_plaid_items_for_linked_banks(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token, _ = _make_admin(client, register_and_login, db, "admin-delete-plaid@example.com")
    _, target_id = register_and_login("delete-target-plaid@example.com")

    # Pre-mark removed_at so the delete path's idempotent skip is exercised without needing
    # real Plaid sandbox credentials — the actual item/remove call itself is covered by
    # banks/tests/test_unlink_idempotency.py and the sandbox integration suite.
    item = PlaidItem(
        access_token="irrelevant-for-this-test",
        item_id=f"item-{uuid.uuid4()}",
        institution_id="ins_1",
        institution_name="Sandbox Bank",
        removed_at=datetime.now(UTC),
    )
    db.add(item)
    db.flush()
    bank = Bank(owner_id=target_id, plaid_item_id=item.id)
    db.add(bank)
    db.commit()
    bank_id = bank.id  # captured before the DELETE below removes the row out from under `db`

    resp = client.request(
        "DELETE",
        f"/api/v1/admin/users/{target_id}",
        json={"confirm": True},
        headers=_auth_headers(admin_token),
    )
    assert resp.status_code == 204
    db.expire_all()
    assert db.scalar(select(User).where(User.id == target_id)) is None
    assert db.scalar(select(Bank).where(Bank.id == bank_id)) is None
