import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from app.auth.models import User
from app.notifications import service


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_list_notifications_and_unread_only_filter(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: DbSession,
) -> None:
    token, user_id = register_and_login("notif-list@example.com")
    user = db.get(User, user_id)
    assert user is not None
    service.create_notification(db, user.id, "test_type", "Title one", "Body one")
    unread_two = service.create_notification(db, user.id, "test_type", "Title two", "Body two")
    service.set_read(db, user, unread_two.id, True)

    all_resp = client.get("/api/v1/notifications", headers=_auth_headers(token))
    assert len(all_resp.json()["data"]) == 2

    unread_resp = client.get(
        "/api/v1/notifications", params={"unread_only": True}, headers=_auth_headers(token)
    )
    unread_data = unread_resp.json()["data"]
    assert len(unread_data) == 1
    assert unread_data[0]["title"] == "Title one"


def test_mark_read_and_unread(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: DbSession,
) -> None:
    token, user_id = register_and_login("notif-read@example.com")
    user = db.get(User, user_id)
    assert user is not None
    notification = service.create_notification(db, user.id, "test_type", "Title", "Body")

    read_resp = client.patch(
        f"/api/v1/notifications/{notification.id}",
        json={"read": True},
        headers=_auth_headers(token),
    )
    assert read_resp.json()["data"]["read_at"] is not None

    unread_resp = client.patch(
        f"/api/v1/notifications/{notification.id}",
        json={"read": False},
        headers=_auth_headers(token),
    )
    assert unread_resp.json()["data"]["read_at"] is None


def test_dismiss_notification(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: DbSession,
) -> None:
    token, user_id = register_and_login("notif-dismiss@example.com")
    user = db.get(User, user_id)
    assert user is not None
    notification = service.create_notification(db, user.id, "test_type", "Title", "Body")

    assert (
        client.delete(
            f"/api/v1/notifications/{notification.id}", headers=_auth_headers(token)
        ).status_code
        == 204
    )
    assert client.get("/api/v1/notifications", headers=_auth_headers(token)).json()["data"] == []


def test_notifications_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/notifications").status_code == 401


def test_nonexistent_notification_returns_404(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("notif-nobody@example.com")
    resp = client.patch(
        f"/api/v1/notifications/{uuid.uuid4()}",
        json={"read": True},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 404


def test_a_second_users_token_cannot_see_or_modify_the_first_users_notification(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: DbSession,
) -> None:
    owner_token, owner_id = register_and_login("notif-owner@example.com")
    owner = db.get(User, owner_id)
    assert owner is not None
    notification = service.create_notification(db, owner.id, "test_type", "Title", "Body")

    intruder_token, _intruder_id = register_and_login("notif-intruder@example.com")
    intruder_headers = _auth_headers(intruder_token)

    assert (
        client.patch(
            f"/api/v1/notifications/{notification.id}",
            json={"read": True},
            headers=intruder_headers,
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/v1/notifications/{notification.id}", headers=intruder_headers
        ).status_code
        == 404
    )
