import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.metrics.models import Metric


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_patching_current_value_twice_creates_two_metrics_rows_not_one_overwritten_row(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]], db: DbSession
) -> None:
    token, user_id = register_and_login("asset-autowrite@example.com")
    create_resp = client.post(
        "/api/v1/assets",
        json={"name": "House", "asset_type": "real_estate", "current_value": "300000.00"},
        headers=_auth_headers(token),
    )
    asset_id = create_resp.json()["data"]["id"]

    client.patch(
        f"/api/v1/assets/{asset_id}",
        json={"current_value": "310000.00"},
        headers=_auth_headers(token),
    )
    client.patch(
        f"/api/v1/assets/{asset_id}",
        json={"current_value": "320000.00"},
        headers=_auth_headers(token),
    )

    rows = db.scalars(
        select(Metric).where(
            Metric.user_id == user_id,
            Metric.type == "asset_value",
            Metric.asset_id == uuid.UUID(asset_id),
        )
    ).all()
    assert len(rows) == 2
    assert {row.value for row in rows} == {310000, 320000}


def test_patching_current_value_with_the_same_value_writes_no_new_row(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]], db: DbSession
) -> None:
    token, user_id = register_and_login("asset-noop@example.com")
    create_resp = client.post(
        "/api/v1/assets",
        json={"name": "Car", "asset_type": "vehicle", "current_value": "15000.00"},
        headers=_auth_headers(token),
    )
    asset_id = create_resp.json()["data"]["id"]

    client.patch(
        f"/api/v1/assets/{asset_id}",
        json={"current_value": "15000.00"},
        headers=_auth_headers(token),
    )

    rows = db.scalars(
        select(Metric).where(Metric.user_id == user_id, Metric.type == "asset_value")
    ).all()
    assert len(rows) == 0
