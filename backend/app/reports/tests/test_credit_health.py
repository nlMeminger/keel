import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_response_includes_utilization_and_credit_score_history_together(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("credit-health@example.com")
    headers = _auth_headers(token)
    card_id = client.post(
        "/api/v1/accounts",
        json={
            "name": "Rewards card",
            "account_type": "credit_card",
            "balance": "250.00",
            "detail": {"credit_limit": 1000},
        },
        headers=headers,
    ).json()["data"]["id"]
    client.post(
        "/api/v1/metrics",
        json={"type": "credit_score", "value": "700", "date": "2026-01-15"},
        headers=headers,
    )
    client.post(
        "/api/v1/metrics",
        json={"type": "credit_score", "value": "720", "date": "2026-02-15"},
        headers=headers,
    )

    resp = client.get(
        "/api/v1/reports/credit-health",
        params={"granularity": "month", "date_from": "2026-01-01", "date_to": "2026-02-28"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert len(data["accounts"]) == 1
    row = data["accounts"][0]
    assert row["account_id"] == card_id
    assert row["balance"] == "250.00"
    assert row["credit_limit"] == "1000.0"
    assert row["utilization"] == "0.25"
    assert data["overall_utilization"] == "0.25"

    history = data["credit_score_history"]
    assert [(p["date"], p["value"]) for p in history] == [
        ("2026-01-31", "700.00"),
        ("2026-02-28", "720.00"),
    ]


def test_user_with_no_credit_accounts_gets_null_overall_utilization_not_an_error(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("credit-health-empty@example.com")
    resp = client.get("/api/v1/reports/credit-health", headers=_auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["accounts"] == []
    assert data["overall_utilization"] is None
    assert data["credit_score_history"] == []


def test_credit_health_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/reports/credit-health").status_code == 401
