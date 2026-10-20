import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_standalone_metric_with_no_account_or_asset(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("metric-standalone@example.com")
    resp = client.post(
        "/api/v1/metrics",
        json={"type": "credit_score", "value": "720", "date": "2026-01-01"},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["account_id"] is None
    assert data["asset_id"] is None


def test_both_account_and_asset_set_rejected_before_db(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("metric-exclusive@example.com")
    account_resp = client.post(
        "/api/v1/accounts",
        json={"name": "Checking", "account_type": "checking", "balance": "0"},
        headers=_auth_headers(token),
    )
    account_id = account_resp.json()["data"]["id"]
    asset_resp = client.post(
        "/api/v1/assets",
        json={"name": "Car", "asset_type": "vehicle", "current_value": "1"},
        headers=_auth_headers(token),
    )
    asset_id = asset_resp.json()["data"]["id"]

    resp = client.post(
        "/api/v1/metrics",
        json={
            "type": "bogus",
            "value": "1",
            "date": "2026-01-01",
            "account_id": account_id,
            "asset_id": asset_id,
        },
        headers=_auth_headers(token),
    )
    assert resp.status_code == 422


def test_bulk_create_50_entries_in_one_request(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("metric-bulk@example.com")
    entries = [
        {"type": "credit_score", "value": str(700 + i), "date": "2026-01-01"} for i in range(50)
    ]
    resp = client.post(
        "/api/v1/metrics/bulk", json={"entries": entries}, headers=_auth_headers(token)
    )
    assert resp.status_code == 201
    assert len(resp.json()["data"]) == 50

    list_resp = client.get(
        "/api/v1/metrics", params={"page_size": 50}, headers=_auth_headers(token)
    )
    assert list_resp.json()["pagination"]["total_count"] == 50


def test_bulk_create_rejects_whole_batch_on_one_invalid_entry(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("metric-bulk-invalid@example.com")
    entries = [
        {"type": "credit_score", "value": "700", "date": "2026-01-01"},
        {
            "type": "credit_score",
            "value": "710",
            "date": "2026-01-01",
            "account_id": str(uuid.uuid4()),
        },
    ]
    resp = client.post(
        "/api/v1/metrics/bulk", json={"entries": entries}, headers=_auth_headers(token)
    )
    assert resp.status_code == 404

    list_resp = client.get("/api/v1/metrics", headers=_auth_headers(token))
    assert list_resp.json()["data"] == []


def test_update_metric_corrects_a_past_entry(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("metric-corrector@example.com")
    create_resp = client.post(
        "/api/v1/metrics",
        json={"type": "credit_score", "value": "700", "date": "2026-01-01"},
        headers=_auth_headers(token),
    )
    metric_id = create_resp.json()["data"]["id"]

    patch_resp = client.patch(
        f"/api/v1/metrics/{metric_id}", json={"value": "705"}, headers=_auth_headers(token)
    )
    assert patch_resp.json()["data"]["value"] == "705.00"

    list_resp = client.get("/api/v1/metrics", headers=_auth_headers(token))
    assert len(list_resp.json()["data"]) == 1


def test_delete_metric(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("metric-deleter@example.com")
    create_resp = client.post(
        "/api/v1/metrics",
        json={"type": "credit_score", "value": "700", "date": "2026-01-01"},
        headers=_auth_headers(token),
    )
    metric_id = create_resp.json()["data"]["id"]

    assert (
        client.delete(f"/api/v1/metrics/{metric_id}", headers=_auth_headers(token)).status_code
        == 204
    )
    assert client.get("/api/v1/metrics", headers=_auth_headers(token)).json()["data"] == []


def test_metrics_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/metrics").status_code == 401


def test_nonexistent_metric_returns_404(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("metric-nobody@example.com")
    resp = client.patch(
        f"/api/v1/metrics/{uuid.uuid4()}", json={"value": "1"}, headers=_auth_headers(token)
    )
    assert resp.status_code == 404


def test_a_second_users_token_cannot_see_or_modify_the_first_users_metric(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    owner_token, _owner_id = register_and_login("metric-owner@example.com")
    create_resp = client.post(
        "/api/v1/metrics",
        json={"type": "credit_score", "value": "1", "date": "2026-01-01"},
        headers=_auth_headers(owner_token),
    )
    metric_id = create_resp.json()["data"]["id"]

    intruder_token, _intruder_id = register_and_login("metric-intruder@example.com")
    intruder_headers = _auth_headers(intruder_token)

    assert (
        client.patch(
            f"/api/v1/metrics/{metric_id}", json={"value": "999"}, headers=intruder_headers
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/metrics/{metric_id}", headers=intruder_headers).status_code == 404
    )
