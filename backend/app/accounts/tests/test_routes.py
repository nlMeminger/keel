import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_create_and_get_checking_account(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("checker@example.com")
    create_resp = client.post(
        "/api/v1/accounts",
        json={
            "name": "Everyday checking",
            "account_type": "checking",
            "balance": "1500.00",
            "detail": {"overdraft_limit": 100},
        },
        headers=_auth_headers(token),
    )
    assert create_resp.status_code == 201
    account = create_resp.json()["data"]
    assert account["account_type"] == "checking"
    assert account["detail"] == {"overdraft_limit": 100.0}
    assert account["is_active"] is True
    assert account["is_plaid_linked"] is False

    get_resp = client.get(f"/api/v1/accounts/{account['id']}", headers=_auth_headers(token))
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["name"] == "Everyday checking"


def test_create_mortgage_account_with_type_specific_detail(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("mortgagor@example.com")
    resp = client.post(
        "/api/v1/accounts",
        json={
            "name": "Home loan",
            "account_type": "mortgage",
            "balance": "250000.00",
            "detail": {"principal": 260000, "interest_rate": 5.5, "term_months": 360},
        },
        headers=_auth_headers(token),
    )
    assert resp.status_code == 201
    detail = resp.json()["data"]["detail"]
    assert detail["principal"] == 260000.0
    assert detail["term_months"] == 360


def test_detail_mismatched_with_account_type_rejected_before_db(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("badtype@example.com")
    # credit_limit is required for credit_card; omitting it must 422, not 500/201.
    resp = client.post(
        "/api/v1/accounts",
        json={
            "name": "Broken card",
            "account_type": "credit_card",
            "balance": "0",
            "detail": {"apr": 19.99},
        },
        headers=_auth_headers(token),
    )
    assert resp.status_code == 422

    list_resp = client.get("/api/v1/accounts", headers=_auth_headers(token))
    assert list_resp.json()["data"] == []


def test_update_account_name_and_balance(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("updater@example.com")
    create_resp = client.post(
        "/api/v1/accounts",
        json={"name": "Savings", "account_type": "savings", "balance": "100.00"},
        headers=_auth_headers(token),
    )
    account_id = create_resp.json()["data"]["id"]

    patch_resp = client.patch(
        f"/api/v1/accounts/{account_id}",
        json={"name": "Rainy day fund", "balance": "500.00"},
        headers=_auth_headers(token),
    )
    assert patch_resp.status_code == 200
    data = patch_resp.json()["data"]
    assert data["name"] == "Rainy day fund"
    assert data["balance"] == "500.00"


def test_update_account_type_without_matching_detail_rejected(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("switcher@example.com")
    create_resp = client.post(
        "/api/v1/accounts",
        json={"name": "Checking", "account_type": "checking", "balance": "0"},
        headers=_auth_headers(token),
    )
    account_id = create_resp.json()["data"]["id"]

    # Switching to credit_card without supplying the now-required credit_limit must fail.
    patch_resp = client.patch(
        f"/api/v1/accounts/{account_id}",
        json={"account_type": "credit_card"},
        headers=_auth_headers(token),
    )
    assert patch_resp.status_code == 422


def test_delete_account_deactivates_rather_than_hard_deletes(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("deactivator@example.com")
    create_resp = client.post(
        "/api/v1/accounts",
        json={"name": "Old account", "account_type": "checking", "balance": "0"},
        headers=_auth_headers(token),
    )
    account_id = create_resp.json()["data"]["id"]

    delete_resp = client.delete(f"/api/v1/accounts/{account_id}", headers=_auth_headers(token))
    assert delete_resp.status_code == 204

    # Still fetchable by id (soft-deactivated, not hard-deleted) ...
    get_resp = client.get(f"/api/v1/accounts/{account_id}", headers=_auth_headers(token))
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["is_active"] is False

    # ... but excluded from the default (active-only) list.
    list_resp = client.get("/api/v1/accounts", headers=_auth_headers(token))
    assert list_resp.json()["data"] == []

    inactive_list_resp = client.get(
        "/api/v1/accounts", params={"active": "false"}, headers=_auth_headers(token)
    )
    assert len(inactive_list_resp.json()["data"]) == 1


def test_list_filters_by_type(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("filterer@example.com")
    client.post(
        "/api/v1/accounts",
        json={"name": "Checking", "account_type": "checking", "balance": "0"},
        headers=_auth_headers(token),
    )
    client.post(
        "/api/v1/accounts",
        json={"name": "Savings", "account_type": "savings", "balance": "0"},
        headers=_auth_headers(token),
    )

    resp = client.get("/api/v1/accounts", params={"type": "savings"}, headers=_auth_headers(token))
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["account_type"] == "savings"


def test_accounts_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/accounts").status_code == 401
    assert client.post("/api/v1/accounts", json={}).status_code == 401


def test_nonexistent_account_returns_404(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("nobody2@example.com")
    resp = client.get(f"/api/v1/accounts/{uuid.uuid4()}", headers=_auth_headers(token))
    assert resp.status_code == 404


def test_a_second_users_token_cannot_see_or_modify_the_first_users_account(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    owner_token, _owner_id = register_and_login("account-owner@example.com")
    create_resp = client.post(
        "/api/v1/accounts",
        json={"name": "Private", "account_type": "checking", "balance": "0"},
        headers=_auth_headers(owner_token),
    )
    account_id = create_resp.json()["data"]["id"]

    intruder_token, _intruder_id = register_and_login("account-intruder@example.com")
    intruder_headers = _auth_headers(intruder_token)

    assert client.get(f"/api/v1/accounts/{account_id}", headers=intruder_headers).status_code == 404
    assert (
        client.patch(
            f"/api/v1/accounts/{account_id}", json={"name": "Stolen"}, headers=intruder_headers
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/accounts/{account_id}", headers=intruder_headers).status_code == 404
    )
