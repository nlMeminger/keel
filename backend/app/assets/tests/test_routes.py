import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_create_and_list_asset(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("asset-creator@example.com")
    resp = client.post(
        "/api/v1/assets",
        json={"name": "Family car", "asset_type": "vehicle", "current_value": "18000.00"},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["name"] == "Family car"
    assert data["current_value"] == "18000.00"

    list_resp = client.get("/api/v1/assets", headers=_auth_headers(token))
    assert len(list_resp.json()["data"]) == 1


def test_update_asset_value(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("asset-updater@example.com")
    create_resp = client.post(
        "/api/v1/assets",
        json={"name": "House", "asset_type": "real_estate", "current_value": "300000.00"},
        headers=_auth_headers(token),
    )
    asset_id = create_resp.json()["data"]["id"]

    patch_resp = client.patch(
        f"/api/v1/assets/{asset_id}",
        json={"current_value": "310000.00"},
        headers=_auth_headers(token),
    )
    assert patch_resp.json()["data"]["current_value"] == "310000.00"
    assert patch_resp.json()["data"]["name"] == "House"


def test_delete_asset(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("asset-deleter@example.com")
    create_resp = client.post(
        "/api/v1/assets",
        json={"name": "Old boat", "asset_type": "vehicle", "current_value": "5000"},
        headers=_auth_headers(token),
    )
    asset_id = create_resp.json()["data"]["id"]

    assert (
        client.delete(f"/api/v1/assets/{asset_id}", headers=_auth_headers(token)).status_code == 204
    )
    assert client.get("/api/v1/assets", headers=_auth_headers(token)).json()["data"] == []


def test_assets_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/assets").status_code == 401


def test_nonexistent_asset_returns_404(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("asset-nobody@example.com")
    resp = client.patch(
        f"/api/v1/assets/{uuid.uuid4()}", json={"name": "x"}, headers=_auth_headers(token)
    )
    assert resp.status_code == 404


def test_a_second_users_token_cannot_see_or_modify_the_first_users_asset(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    owner_token, _owner_id = register_and_login("asset-owner@example.com")
    create_resp = client.post(
        "/api/v1/assets",
        json={"name": "Private asset", "asset_type": "other", "current_value": "1"},
        headers=_auth_headers(owner_token),
    )
    asset_id = create_resp.json()["data"]["id"]

    intruder_token, _intruder_id = register_and_login("asset-intruder@example.com")
    intruder_headers = _auth_headers(intruder_token)

    assert (
        client.patch(
            f"/api/v1/assets/{asset_id}", json={"name": "Stolen"}, headers=intruder_headers
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/assets/{asset_id}", headers=intruder_headers).status_code == 404
