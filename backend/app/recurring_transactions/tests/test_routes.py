import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_recurring(client: TestClient, token: str, name: str = "Netflix") -> str:
    resp = client.post(
        "/api/v1/recurring-transactions",
        json={"name": name, "amount_expected": "15.99", "frequency": "monthly"},
        headers=_auth_headers(token),
    )
    return str(resp.json()["data"]["id"])


def test_create_and_list_recurring(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("recurring-create@example.com")

    create_resp = client.post(
        "/api/v1/recurring-transactions",
        json={
            "name": "Netflix",
            "amount_expected": "15.99",
            "frequency": "monthly",
            "is_bill": False,
        },
        headers=_auth_headers(token),
    )
    assert create_resp.status_code == 201
    row = create_resp.json()["data"]
    assert row["name"] == "Netflix"
    assert row["last_paid_date"] is None

    list_resp = client.get("/api/v1/recurring-transactions", headers=_auth_headers(token))
    assert len(list_resp.json()["data"]) == 1


def test_update_recurring_marks_as_bill_and_adjusts_amount(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("recurring-update@example.com")
    recurring_id = _create_recurring(client, token)

    patch_resp = client.patch(
        f"/api/v1/recurring-transactions/{recurring_id}",
        json={"is_bill": True, "amount_expected": "17.99"},
        headers=_auth_headers(token),
    )
    data = patch_resp.json()["data"]
    assert data["is_bill"] is True
    assert data["amount_expected"] == "17.99"


def test_recording_a_payment_updates_last_paid_date(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("recurring-payment@example.com")
    recurring_id = _create_recurring(client, token)

    payment_resp = client.post(
        f"/api/v1/recurring-transactions/{recurring_id}/payments",
        json={"amount": "15.99", "date": "2026-01-05"},
        headers=_auth_headers(token),
    )
    assert payment_resp.status_code == 201
    assert payment_resp.json()["data"]["last_paid_date"] == "2026-01-05"

    # Visible on the next GET without a second fetch of anything else.
    list_resp = client.get("/api/v1/recurring-transactions", headers=_auth_headers(token))
    row = next(r for r in list_resp.json()["data"] if r["id"] == recurring_id)
    assert row["last_paid_date"] == "2026-01-05"

    # An older payment must not regress last_paid_date.
    client.post(
        f"/api/v1/recurring-transactions/{recurring_id}/payments",
        json={"amount": "15.99", "date": "2025-12-05"},
        headers=_auth_headers(token),
    )
    after_resp = client.get("/api/v1/recurring-transactions", headers=_auth_headers(token))
    after_row = next(r for r in after_resp.json()["data"] if r["id"] == recurring_id)
    assert after_row["last_paid_date"] == "2026-01-05"


def test_delete_recurring(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("recurring-delete@example.com")
    recurring_id = _create_recurring(client, token)

    assert (
        client.delete(
            f"/api/v1/recurring-transactions/{recurring_id}", headers=_auth_headers(token)
        ).status_code
        == 204
    )
    assert (
        client.get("/api/v1/recurring-transactions", headers=_auth_headers(token)).json()["data"]
        == []
    )


def test_recurring_transactions_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/recurring-transactions").status_code == 401


def test_nonexistent_recurring_returns_404(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("recurring-nobody@example.com")
    resp = client.patch(
        f"/api/v1/recurring-transactions/{uuid.uuid4()}",
        json={"is_bill": True},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 404


def test_a_second_users_token_cannot_see_or_modify_the_first_users_recurring(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    owner_token, _owner_id = register_and_login("recurring-owner@example.com")
    recurring_id = _create_recurring(client, owner_token)

    intruder_token, _intruder_id = register_and_login("recurring-intruder@example.com")
    intruder_headers = _auth_headers(intruder_token)

    assert (
        client.patch(
            f"/api/v1/recurring-transactions/{recurring_id}",
            json={"is_bill": True},
            headers=intruder_headers,
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/recurring-transactions/{recurring_id}/payments",
            json={"amount": "1", "date": "2026-01-01"},
            headers=intruder_headers,
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/v1/recurring-transactions/{recurring_id}", headers=intruder_headers
        ).status_code
        == 404
    )
