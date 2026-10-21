import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_per_holding_performance_for_manually_entered_holdings(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("investments@example.com")
    headers = _auth_headers(token)
    account_id = client.post(
        "/api/v1/accounts",
        json={"name": "Brokerage", "account_type": "investment", "balance": "0"},
        headers=headers,
    ).json()["data"]["id"]
    holding_id = client.post(
        f"/api/v1/accounts/{account_id}/holdings",
        json={
            "symbol": "VTI",
            "name": "Vanguard Total Market",
            "quantity": "10",
            "cost_basis": "2000.00",
        },
        headers=headers,
    ).json()["data"]["id"]
    client.patch(
        f"/api/v1/accounts/{account_id}/holdings/{holding_id}",
        json={"current_value": "2500.00"},
        headers=headers,
    )

    resp = client.get("/api/v1/reports/investments", headers=headers)
    assert resp.status_code == 200
    rows = resp.json()["data"]
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == holding_id
    assert row["account_id"] == account_id
    assert row["cost_basis"] == "2000.00"
    assert row["current_value"] == "2500.00"
    assert row["gain_loss"] == "500.00"
    assert row["source"] == "manual"


def test_user_with_no_holdings_gets_empty_but_correctly_shaped_response(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("investments-empty@example.com")
    resp = client.get("/api/v1/reports/investments", headers=_auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["data"] == []


def test_a_holding_with_no_current_value_yet_reports_null_gain_loss(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("investments-no-value@example.com")
    headers = _auth_headers(token)
    account_id = client.post(
        "/api/v1/accounts",
        json={"name": "Brokerage", "account_type": "investment", "balance": "0"},
        headers=headers,
    ).json()["data"]["id"]
    client.post(
        f"/api/v1/accounts/{account_id}/holdings",
        json={
            "symbol": "VTI",
            "name": "Vanguard Total Market",
            "quantity": "5",
            "cost_basis": "900.00",
        },
        headers=headers,
    )

    resp = client.get("/api/v1/reports/investments", headers=headers)
    row = resp.json()["data"][0]
    assert row["current_value"] is None
    assert row["gain_loss"] is None


def test_investments_only_includes_the_callers_own_holdings(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    owner_token, _owner_id = register_and_login("investments-owner@example.com")
    owner_headers = _auth_headers(owner_token)
    account_id = client.post(
        "/api/v1/accounts",
        json={"name": "Brokerage", "account_type": "investment", "balance": "0"},
        headers=owner_headers,
    ).json()["data"]["id"]
    client.post(
        f"/api/v1/accounts/{account_id}/holdings",
        json={
            "symbol": "VTI",
            "name": "Vanguard Total Market",
            "quantity": "5",
            "cost_basis": "900.00",
        },
        headers=owner_headers,
    )

    intruder_token, _intruder_id = register_and_login("investments-intruder@example.com")
    resp = client.get("/api/v1/reports/investments", headers=_auth_headers(intruder_token))
    assert resp.json()["data"] == []


def test_investments_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/reports/investments").status_code == 401
