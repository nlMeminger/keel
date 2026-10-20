import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.metrics.models import Metric


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_patching_balance_twice_creates_two_metrics_rows_not_one_overwritten_row(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]], db: DbSession
) -> None:
    token, user_id = register_and_login("balance-autowrite@example.com")
    create_resp = client.post(
        "/api/v1/accounts",
        json={"name": "Checking", "account_type": "checking", "balance": "100.00"},
        headers=_auth_headers(token),
    )
    account_id = create_resp.json()["data"]["id"]

    client.patch(
        f"/api/v1/accounts/{account_id}", json={"balance": "150.00"}, headers=_auth_headers(token)
    )
    client.patch(
        f"/api/v1/accounts/{account_id}", json={"balance": "200.00"}, headers=_auth_headers(token)
    )

    rows = db.scalars(
        select(Metric).where(
            Metric.user_id == user_id,
            Metric.type == "account_balance",
            Metric.account_id == uuid.UUID(account_id),
        )
    ).all()
    assert len(rows) == 2
    assert {row.value for row in rows} == {150, 200}


def test_patching_balance_with_the_same_value_writes_no_new_row(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]], db: DbSession
) -> None:
    token, user_id = register_and_login("balance-noop@example.com")
    create_resp = client.post(
        "/api/v1/accounts",
        json={"name": "Checking", "account_type": "checking", "balance": "100.00"},
        headers=_auth_headers(token),
    )
    account_id = create_resp.json()["data"]["id"]

    client.patch(
        f"/api/v1/accounts/{account_id}", json={"balance": "100.00"}, headers=_auth_headers(token)
    )

    rows = db.scalars(
        select(Metric).where(Metric.user_id == user_id, Metric.type == "account_balance")
    ).all()
    assert len(rows) == 0


def test_patching_name_only_does_not_write_a_metric(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]], db: DbSession
) -> None:
    token, user_id = register_and_login("balance-name-only@example.com")
    create_resp = client.post(
        "/api/v1/accounts",
        json={"name": "Checking", "account_type": "checking", "balance": "100.00"},
        headers=_auth_headers(token),
    )
    account_id = create_resp.json()["data"]["id"]

    client.patch(
        f"/api/v1/accounts/{account_id}", json={"name": "Renamed"}, headers=_auth_headers(token)
    )

    rows = db.scalars(
        select(Metric).where(Metric.user_id == user_id, Metric.type == "account_balance")
    ).all()
    assert len(rows) == 0
