import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_account(client: TestClient, token: str, name: str = "Checking") -> str:
    resp = client.post(
        "/api/v1/accounts",
        json={"name": name, "account_type": "checking", "balance": "0"},
        headers=_auth_headers(token),
    )
    return str(resp.json()["data"]["id"])


def _create_txn(
    client: TestClient, token: str, account_id: str, amount: str, txn_date: str, **extra: object
) -> dict[str, object]:
    resp = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "amount": amount,
            "description": "x",
            "date": txn_date,
            **extra,
        },
        headers=_auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert isinstance(data, dict)
    return data


def test_cash_flow_totals_match_hand_computation_and_exclude_confirmed_transfer(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("cash-flow@example.com")
    headers = _auth_headers(token)
    checking = _create_account(client, token, "Checking")
    savings = _create_account(client, token, "Savings")

    _create_txn(client, token, checking, "1000.00", "2026-03-01")  # paycheck
    _create_txn(client, token, checking, "-200.00", "2026-03-02")  # groceries
    # A same-amount, opposite-sign, adjacent-day pair -> auto-suggested as a transfer.
    out_txn = _create_txn(client, token, checking, "-300.00", "2026-03-04")
    in_txn = _create_txn(client, token, savings, "300.00", "2026-03-05")
    assert in_txn["transfer_status"] == "suggested"

    confirm_resp = client.patch(
        f"/api/v1/transactions/{out_txn['id']}",
        json={"transfer_status": "confirmed"},
        headers=headers,
    )
    assert confirm_resp.json()["data"]["is_transfer"] is True

    resp = client.get(
        "/api/v1/reports/cash-flow",
        params={"granularity": "month", "date_from": "2026-03-01", "date_to": "2026-03-31"},
        headers=headers,
    )
    assert resp.status_code == 200
    points = resp.json()["data"]
    assert len(points) == 1
    # Inflow: 1000 (the 300 transfer-in is excluded). Outflow: 200 (the 300 transfer-out
    # is excluded too), even though both sides still carry the "Transfer" category and
    # remain visible on the plain transaction list.
    assert points[0]["inflow"] == "1000.00"
    assert points[0]["outflow"] == "200.00"

    list_resp = client.get("/api/v1/transactions", headers=headers)
    listed_ids = {row["id"] for row in list_resp.json()["data"]}
    assert out_txn["id"] in listed_ids
    assert in_txn["id"] in listed_ids


def test_spending_by_category_totals_match_hand_computation_and_exclude_confirmed_transfer(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("spending-by-category@example.com")
    headers = _auth_headers(token)
    checking = _create_account(client, token, "Checking")
    savings = _create_account(client, token, "Savings")

    category_id = client.post(
        "/api/v1/categories", json={"primary_category": "Groceries"}, headers=headers
    ).json()["data"]["id"]

    _create_txn(client, token, checking, "-60.00", "2026-04-01", category_id=category_id)
    _create_txn(client, token, checking, "-15.00", "2026-04-02")  # uncategorized
    out_txn = _create_txn(client, token, checking, "-500.00", "2026-04-06")  # Monday
    _create_txn(client, token, savings, "500.00", "2026-04-07")  # Tuesday
    confirm_resp = client.patch(
        f"/api/v1/transactions/{out_txn['id']}",
        json={"transfer_status": "confirmed"},
        headers=headers,
    )
    assert confirm_resp.json()["data"]["is_transfer"] is True

    resp = client.get(
        "/api/v1/reports/spending-by-category",
        params={"date_from": "2026-04-01", "date_to": "2026-04-30"},
        headers=headers,
    )
    assert resp.status_code == 200
    rows = {row["category_id"]: row["total"] for row in resp.json()["data"]}
    assert rows[category_id] == "60.00"
    assert rows[None] == "15.00"
    assert len(rows) == 2


def test_reports_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/reports/cash-flow").status_code == 401
    assert client.get("/api/v1/reports/spending-by-category").status_code == 401
