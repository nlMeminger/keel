from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.auth.models import Session as SessionModel


def test_full_auth_flow_register_login_me_refresh_rotation_logout(client: TestClient) -> None:
    # Register.
    register_resp = client.post(
        "/api/v1/auth/register",
        json={"email": "walker@example.com", "password": "correct-password", "name": "Walker"},
    )
    assert register_resp.status_code == 201
    assert register_resp.json()["data"]["email"] == "walker@example.com"

    # Login creates a session and sets the refresh cookie.
    login_resp = client.post(
        "/api/v1/auth/login", json={"email": "walker@example.com", "password": "correct-password"}
    )
    assert login_resp.status_code == 200
    access_token = login_resp.json()["data"]["access_token"]
    assert "refresh_token" in client.cookies

    # GET /auth/me with the access token.
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["data"]["email"] == "walker@example.com"

    # Refresh rotates the token: old refresh token stops working afterward.
    old_refresh_cookie = client.cookies["refresh_token"]
    refresh_resp = client.post("/api/v1/auth/refresh")
    assert refresh_resp.status_code == 200
    new_access_token = refresh_resp.json()["data"]["access_token"]
    new_refresh_cookie = client.cookies["refresh_token"]
    assert new_refresh_cookie != old_refresh_cookie

    # Replaying the old (now-revoked) refresh token is rejected (theft detection).
    client.cookies.set("refresh_token", old_refresh_cookie)
    replay_resp = client.post("/api/v1/auth/refresh")
    assert replay_resp.status_code == 401
    client.cookies.set("refresh_token", new_refresh_cookie)

    # Logout revokes the current session.
    logout_resp = client.post(
        "/api/v1/auth/logout", headers={"Authorization": f"Bearer {new_access_token}"}
    )
    assert logout_resp.status_code == 200

    # Further refresh with the now-logged-out token is rejected.
    further_refresh = client.post("/api/v1/auth/refresh")
    assert further_refresh.status_code == 401


def test_replayed_revoked_token_revokes_whole_family(client: TestClient, db: DbSession) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "family@example.com", "password": "correct-password", "name": "Fam"},
    )
    client.post(
        "/api/v1/auth/login", json={"email": "family@example.com", "password": "correct-password"}
    )
    original_cookie = client.cookies["refresh_token"]

    # Rotate once: the original token is now revoked, a new one takes its place.
    client.post("/api/v1/auth/refresh")

    # Replay the original (revoked) token — should revoke the entire family.
    client.cookies.set("refresh_token", original_cookie)
    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401

    sessions = db.scalars(select(SessionModel)).all()
    assert len(sessions) >= 2
    assert all(s.revoked_at is not None for s in sessions)


def test_register_duplicate_email_rejected(client: TestClient) -> None:
    payload = {"email": "dupe@example.com", "password": "correct-password", "name": "Dupe"}
    first = client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201
    second = client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409


def test_login_wrong_password_rejected(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "wrongpw@example.com", "password": "correct-password", "name": "WP"},
    )
    resp = client.post(
        "/api/v1/auth/login", json={"email": "wrongpw@example.com", "password": "nope-nope"}
    )
    assert resp.status_code == 401


def test_me_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_a_second_users_token_cannot_see_the_first_users_me(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "user-a@example.com", "password": "correct-password", "name": "A"},
    )
    login_a = client.post(
        "/api/v1/auth/login", json={"email": "user-a@example.com", "password": "correct-password"}
    )
    token_a = login_a.json()["data"]["access_token"]

    client.post(
        "/api/v1/auth/register",
        json={"email": "user-b@example.com", "password": "correct-password", "name": "B"},
    )
    login_b = client.post(
        "/api/v1/auth/login", json={"email": "user-b@example.com", "password": "correct-password"}
    )
    token_b = login_b.json()["data"]["access_token"]

    resp_a = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_a}"})
    resp_b = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_b}"})

    assert resp_a.json()["data"]["email"] == "user-a@example.com"
    assert resp_b.json()["data"]["email"] == "user-b@example.com"
    assert resp_a.json()["data"]["id"] != resp_b.json()["data"]["id"]


def test_sessions_list_revoke_and_revoke_others(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "sessions@example.com", "password": "correct-password", "name": "S"},
    )
    login_resp = client.post(
        "/api/v1/auth/login", json={"email": "sessions@example.com", "password": "correct-password"}
    )
    token = login_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    sessions_resp = client.get("/api/v1/auth/sessions", headers=headers)
    assert sessions_resp.status_code == 200
    sessions = sessions_resp.json()["data"]
    assert len(sessions) == 1
    assert sessions[0]["is_current"] is True

    # Revoke-others with only one active session is a no-op.
    revoke_others_resp = client.delete("/api/v1/auth/sessions", headers=headers)
    assert revoke_others_resp.status_code == 200
    sessions_after = client.get("/api/v1/auth/sessions", headers=headers).json()["data"]
    assert len(sessions_after) == 1

    session_id = sessions_after[0]["id"]
    delete_resp = client.delete(f"/api/v1/auth/sessions/{session_id}", headers=headers)
    assert delete_resp.status_code == 204


def test_cannot_revoke_another_users_session(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "owner@example.com", "password": "correct-password", "name": "Owner"},
    )
    owner_login = client.post(
        "/api/v1/auth/login", json={"email": "owner@example.com", "password": "correct-password"}
    )
    owner_token = owner_login.json()["data"]["access_token"]
    owner_sessions = client.get(
        "/api/v1/auth/sessions", headers={"Authorization": f"Bearer {owner_token}"}
    ).json()["data"]
    owner_session_id = owner_sessions[0]["id"]

    client.cookies.clear()
    client.post(
        "/api/v1/auth/register",
        json={"email": "intruder@example.com", "password": "correct-password", "name": "Intruder"},
    )
    intruder_login = client.post(
        "/api/v1/auth/login",
        json={"email": "intruder@example.com", "password": "correct-password"},
    )
    intruder_token = intruder_login.json()["data"]["access_token"]

    resp = client.delete(
        f"/api/v1/auth/sessions/{owner_session_id}",
        headers={"Authorization": f"Bearer {intruder_token}"},
    )
    assert resp.status_code == 404


def test_patch_me_updates_name_and_timezone(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "patch@example.com", "password": "correct-password", "name": "Original"},
    )
    login_resp = client.post(
        "/api/v1/auth/login", json={"email": "patch@example.com", "password": "correct-password"}
    )
    token = login_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    patch_resp = client.patch(
        "/api/v1/auth/me", json={"name": "Updated", "timezone": "America/New_York"}, headers=headers
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["data"]["name"] == "Updated"
    assert patch_resp.json()["data"]["timezone"] == "America/New_York"
