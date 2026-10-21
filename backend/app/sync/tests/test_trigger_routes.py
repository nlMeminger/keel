import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

from app.banks.models import Bank, PlaidItem


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_bank(db: OrmSession, owner_id: uuid.UUID) -> Bank:
    item = PlaidItem(
        access_token="irrelevant-for-this-test",
        item_id=f"item-{uuid.uuid4()}",
        institution_id="ins_1",
        institution_name="Sandbox Bank",
    )
    db.add(item)
    db.flush()
    bank = Bank(owner_id=owner_id, plaid_item_id=item.id)
    db.add(bank)
    db.commit()
    db.refresh(bank)
    return bank


def test_sync_routes_require_auth(client: TestClient) -> None:
    assert client.post("/api/v1/sync/transactions").status_code == 401
    assert client.post("/api/v1/sync/balances").status_code == 401


def test_trigger_transaction_sync_with_no_banks_succeeds_trivially(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("no-banks-sync@example.com")
    resp = client.post("/api/v1/sync/transactions", headers=_auth_headers(token))
    assert resp.status_code == 202
    job_id = resp.json()["data"]["job_id"]

    job_status = client.get(f"/api/v1/sync/jobs/{job_id}", headers=_auth_headers(token)).json()[
        "data"
    ]
    assert job_status["status"] == "succeeded"


def test_trigger_balance_sync_with_no_banks_succeeds_trivially(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("no-banks-balance-sync@example.com")
    resp = client.post("/api/v1/sync/balances", headers=_auth_headers(token))
    assert resp.status_code == 202
    job_id = resp.json()["data"]["job_id"]

    job_status = client.get(f"/api/v1/sync/jobs/{job_id}", headers=_auth_headers(token)).json()[
        "data"
    ]
    assert job_status["status"] == "succeeded"


def test_trigger_transaction_sync_404_for_another_users_bank(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    owner_token, owner_id = register_and_login("sync-bank-owner@example.com")
    bank = _make_bank(db, owner_id)

    intruder_token, _intruder_id = register_and_login("sync-bank-intruder@example.com")
    resp = client.post(
        "/api/v1/sync/transactions",
        json={"bank_id": str(bank.id)},
        headers=_auth_headers(intruder_token),
    )
    assert resp.status_code == 404


def test_trigger_balance_sync_404_for_another_users_bank(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    owner_token, owner_id = register_and_login("sync-balance-owner@example.com")
    bank = _make_bank(db, owner_id)

    intruder_token, _intruder_id = register_and_login("sync-balance-intruder@example.com")
    resp = client.post(
        "/api/v1/sync/balances",
        json={"bank_id": str(bank.id)},
        headers=_auth_headers(intruder_token),
    )
    assert resp.status_code == 404
