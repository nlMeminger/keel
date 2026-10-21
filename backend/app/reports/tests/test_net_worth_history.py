import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_month_granularity_matches_hand_computed_net_worth_across_two_months(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("net-worth-history@example.com")
    headers = _auth_headers(token)
    checking_id = client.post(
        "/api/v1/accounts",
        json={"name": "Checking", "account_type": "checking", "balance": "0"},
        headers=headers,
    ).json()["data"]["id"]
    credit_card_id = client.post(
        "/api/v1/accounts",
        json={
            "name": "Card",
            "account_type": "credit_card",
            "balance": "0",
            "detail": {"credit_limit": 1000},
        },
        headers=headers,
    ).json()["data"]["id"]
    car_id = client.post(
        "/api/v1/assets",
        json={"name": "Car", "asset_type": "vehicle", "current_value": "0"},
        headers=headers,
    ).json()["data"]["id"]

    def _backfill(metric_type: str, value: str, metric_date: str, **ref: str) -> None:
        resp = client.post(
            "/api/v1/metrics",
            json={"type": metric_type, "value": value, "date": metric_date, **ref},
            headers=headers,
        )
        assert resp.status_code == 201

    # January: checking 1000, card 200 owed, car worth 5000 -> net worth 1000 - 200 + 5000 = 5800
    _backfill("asset_value", "5000.00", "2026-01-10", asset_id=car_id)
    _backfill("account_balance", "1000.00", "2026-01-15", account_id=checking_id)
    _backfill("account_balance", "200.00", "2026-01-20", account_id=credit_card_id)
    # February: only checking moves to 1500 -> net worth 1500 - 200 + 5000 = 6300
    _backfill("account_balance", "1500.00", "2026-02-10", account_id=checking_id)

    resp = client.get(
        "/api/v1/reports/net-worth-history",
        params={"granularity": "month", "date_from": "2026-01-01", "date_to": "2026-02-28"},
        headers=headers,
    )
    assert resp.status_code == 200
    points = resp.json()["data"]
    assert [(p["date"], p["net_worth"]) for p in points] == [
        ("2026-01-31", "5800.00"),
        ("2026-02-28", "6300.00"),
    ]


def test_an_account_with_no_metrics_yet_contributes_nothing(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("net-worth-no-history@example.com")
    headers = _auth_headers(token)
    # Created but never patched — balance auto-write (4.9) never fires, so this account has
    # no account_balance Metric at all yet.
    client.post(
        "/api/v1/accounts",
        json={"name": "Checking", "account_type": "checking", "balance": "500.00"},
        headers=headers,
    )

    resp = client.get(
        "/api/v1/reports/net-worth-history",
        params={"granularity": "day", "date_from": "2026-01-01", "date_to": "2026-01-01"},
        headers=headers,
    )
    assert resp.json()["data"] == [{"date": "2026-01-01", "net_worth": "0"}]


def test_net_worth_history_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/reports/net-worth-history").status_code == 401
