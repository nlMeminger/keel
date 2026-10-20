import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_create_goal_with_zero_progress(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("goal-creator@example.com")
    resp = client.post(
        "/api/v1/goals",
        json={"name": "Emergency fund", "target_amount": "5000.00", "target_date": "2026-12-31"},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["progress_amount"] == "0"


def test_two_contributions_sum_correctly_visible_on_get_without_separate_fetch(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("goal-contributor@example.com")
    create_resp = client.post(
        "/api/v1/goals",
        json={"name": "Vacation", "target_amount": "2000.00"},
        headers=_auth_headers(token),
    )
    goal_id = create_resp.json()["data"]["id"]

    first = client.post(
        f"/api/v1/goals/{goal_id}/contributions",
        json={"amount": "300.00", "date": "2026-01-01"},
        headers=_auth_headers(token),
    )
    assert first.status_code == 201
    assert first.json()["data"]["progress_amount"] == "300.00"

    second = client.post(
        f"/api/v1/goals/{goal_id}/contributions",
        json={"amount": "150.00", "date": "2026-02-01", "note": "bonus"},
        headers=_auth_headers(token),
    )
    assert second.json()["data"]["progress_amount"] == "450.00"

    # GET /goals inlines the computed progress — no separate contributions fetch needed.
    list_resp = client.get("/api/v1/goals", headers=_auth_headers(token))
    goal_row = next(row for row in list_resp.json()["data"] if row["id"] == goal_id)
    assert goal_row["progress_amount"] == "450.00"


def test_update_goal_target(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("goal-updater@example.com")
    create_resp = client.post(
        "/api/v1/goals",
        json={"name": "Car", "target_amount": "10000.00"},
        headers=_auth_headers(token),
    )
    goal_id = create_resp.json()["data"]["id"]

    patch_resp = client.patch(
        f"/api/v1/goals/{goal_id}", json={"target_amount": "12000.00"}, headers=_auth_headers(token)
    )
    assert patch_resp.json()["data"]["target_amount"] == "12000.00"


def test_delete_goal(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("goal-deleter@example.com")
    create_resp = client.post(
        "/api/v1/goals",
        json={"name": "Temp", "target_amount": "100.00"},
        headers=_auth_headers(token),
    )
    goal_id = create_resp.json()["data"]["id"]

    assert (
        client.delete(f"/api/v1/goals/{goal_id}", headers=_auth_headers(token)).status_code == 204
    )
    assert client.get("/api/v1/goals", headers=_auth_headers(token)).json()["data"] == []


def test_goals_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/goals").status_code == 401


def test_nonexistent_goal_returns_404(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("goal-nobody@example.com")
    resp = client.patch(
        f"/api/v1/goals/{uuid.uuid4()}", json={"name": "x"}, headers=_auth_headers(token)
    )
    assert resp.status_code == 404


def test_contribution_to_nonexistent_goal_returns_404(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("goal-contrib-nobody@example.com")
    resp = client.post(
        f"/api/v1/goals/{uuid.uuid4()}/contributions",
        json={"amount": "10", "date": "2026-01-01"},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 404


def test_a_second_users_token_cannot_see_modify_or_contribute_to_the_first_users_goal(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    owner_token, _owner_id = register_and_login("goal-owner@example.com")
    create_resp = client.post(
        "/api/v1/goals",
        json={"name": "Private goal", "target_amount": "100.00"},
        headers=_auth_headers(owner_token),
    )
    goal_id = create_resp.json()["data"]["id"]

    intruder_token, _intruder_id = register_and_login("goal-intruder@example.com")
    intruder_headers = _auth_headers(intruder_token)

    assert (
        client.patch(
            f"/api/v1/goals/{goal_id}", json={"name": "Stolen"}, headers=intruder_headers
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/goals/{goal_id}", headers=intruder_headers).status_code == 404
    assert (
        client.post(
            f"/api/v1/goals/{goal_id}/contributions",
            json={"amount": "1", "date": "2026-01-01"},
            headers=intruder_headers,
        ).status_code
        == 404
    )
