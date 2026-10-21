import uuid
from collections.abc import Callable
from datetime import date

from fastapi.testclient import TestClient


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _today_in_current_month(day: int = 5) -> str:
    return date.today().replace(day=min(day, 28)).isoformat()


def test_summary_matches_independently_computed_values(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("dashboard@example.com")
    headers = _auth_headers(token)

    checking_id = client.post(
        "/api/v1/accounts",
        json={"name": "Checking", "account_type": "checking", "balance": "1000.00"},
        headers=headers,
    ).json()["data"]["id"]
    client.post(
        "/api/v1/accounts",
        json={
            "name": "Card",
            "account_type": "credit_card",
            "balance": "200.00",
            "detail": {"credit_limit": 1000},
        },
        headers=headers,
    )
    client.post(
        "/api/v1/budgets",
        json={"amount_limit": "500.00", "start_date": _today_in_current_month(1)},
        headers=headers,
    )
    income = client.post(
        "/api/v1/transactions",
        json={
            "account_id": checking_id,
            "amount": "300.00",
            "description": "Paycheck",
            "date": _today_in_current_month(2),
        },
        headers=headers,
    ).json()["data"]
    expense = client.post(
        "/api/v1/transactions",
        json={
            "account_id": checking_id,
            "amount": "-50.00",
            "description": "Groceries",
            "date": _today_in_current_month(3),
        },
        headers=headers,
    ).json()["data"]

    resp = client.get("/api/v1/dashboard/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]

    # checking(1000) - card(200), no assets.
    assert data["net_worth"] == "800.00"
    assert data["this_month_inflow"] == "300.00"
    assert data["this_month_outflow"] == "50.00"

    recent_ids = [row["id"] for row in data["recent_transactions"]]
    assert recent_ids == [expense["id"], income["id"]]

    assert len(data["budgets"]) == 1
    assert data["budgets"][0]["spend_so_far"] == "50.00"
    assert data["budgets"][0]["amount_limit"] == "500.00"

    assert data["latest_credit_score"] is None


def test_latest_credit_score_includes_trend_once_a_second_reading_exists(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("dashboard-credit-score@example.com")
    headers = _auth_headers(token)

    first = client.get("/api/v1/dashboard/summary", headers=headers).json()["data"]
    assert first["latest_credit_score"] is None

    client.post(
        "/api/v1/metrics",
        json={"type": "credit_score", "value": "680", "date": "2026-01-01"},
        headers=headers,
    )
    one_reading = client.get("/api/v1/dashboard/summary", headers=headers).json()["data"]
    assert one_reading["latest_credit_score"]["value"] == "680.00"
    assert one_reading["latest_credit_score"]["trend"] is None

    client.post(
        "/api/v1/metrics",
        json={"type": "credit_score", "value": "710", "date": "2026-02-01"},
        headers=headers,
    )
    two_readings = client.get("/api/v1/dashboard/summary", headers=headers).json()["data"]
    assert two_readings["latest_credit_score"]["value"] == "710.00"
    assert two_readings["latest_credit_score"]["trend"] == "up"


def test_brand_new_user_gets_a_sensible_empty_summary_not_an_error(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("dashboard-empty@example.com")
    resp = client.get("/api/v1/dashboard/summary", headers=_auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["net_worth"] == "0"
    assert data["this_month_inflow"] == "0"
    assert data["this_month_outflow"] == "0"
    assert data["recent_transactions"] == []
    assert data["budgets"] == []
    assert data["latest_credit_score"] is None


def test_dashboard_summary_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/dashboard/summary").status_code == 401
