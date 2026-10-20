import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_create_merchant_with_aliases(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("merchant-creator@example.com")
    resp = client.post(
        "/api/v1/merchants",
        json={"name": "Coffee Co", "aliases": ["COFFEE CO #123", "COFFEECO ONLINE"]},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["name"] == "Coffee Co"
    assert data["aliases"] == ["COFFEE CO #123", "COFFEECO ONLINE"]


def test_list_merchants(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("merchant-lister@example.com")
    client.post("/api/v1/merchants", json={"name": "Grocery"}, headers=_auth_headers(token))
    client.post("/api/v1/merchants", json={"name": "Gas"}, headers=_auth_headers(token))

    resp = client.get("/api/v1/merchants", headers=_auth_headers(token))
    assert len(resp.json()["data"]) == 2


def test_update_merchant_aliases(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("merchant-updater@example.com")
    create_resp = client.post(
        "/api/v1/merchants", json={"name": "Streaming Co"}, headers=_auth_headers(token)
    )
    merchant_id = create_resp.json()["data"]["id"]

    patch_resp = client.patch(
        f"/api/v1/merchants/{merchant_id}",
        json={"aliases": ["STREAMCO", "STREAM CO MONTHLY"]},
        headers=_auth_headers(token),
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["data"]["aliases"] == ["STREAMCO", "STREAM CO MONTHLY"]
    assert patch_resp.json()["data"]["name"] == "Streaming Co"


def test_delete_merchant(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("merchant-deleter@example.com")
    create_resp = client.post(
        "/api/v1/merchants", json={"name": "Temp"}, headers=_auth_headers(token)
    )
    merchant_id = create_resp.json()["data"]["id"]

    assert (
        client.delete(f"/api/v1/merchants/{merchant_id}", headers=_auth_headers(token)).status_code
        == 204
    )
    assert client.get("/api/v1/merchants", headers=_auth_headers(token)).json()["data"] == []


def test_merchants_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/merchants").status_code == 401


def test_nonexistent_merchant_returns_404(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("merchant-nobody@example.com")
    resp = client.patch(
        f"/api/v1/merchants/{uuid.uuid4()}", json={"name": "x"}, headers=_auth_headers(token)
    )
    assert resp.status_code == 404


def test_a_second_users_token_cannot_see_or_modify_the_first_users_merchant(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    owner_token, _owner_id = register_and_login("merchant-owner@example.com")
    create_resp = client.post(
        "/api/v1/merchants", json={"name": "Private Merchant"}, headers=_auth_headers(owner_token)
    )
    merchant_id = create_resp.json()["data"]["id"]

    intruder_token, _intruder_id = register_and_login("merchant-intruder@example.com")
    intruder_headers = _auth_headers(intruder_token)

    assert (
        client.patch(
            f"/api/v1/merchants/{merchant_id}", json={"name": "Stolen"}, headers=intruder_headers
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/merchants/{merchant_id}", headers=intruder_headers).status_code
        == 404
    )
