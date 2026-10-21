import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

from app.auth.models import User
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


def test_banks_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/banks").status_code == 401
    assert client.get(f"/api/v1/banks/{uuid.uuid4()}").status_code == 401
    assert client.post(f"/api/v1/banks/{uuid.uuid4()}/sync").status_code == 401


def test_sync_bank_404_for_nonexistent_bank(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("sync-404@example.com")
    resp = client.post(f"/api/v1/banks/{uuid.uuid4()}/sync", headers=_auth_headers(token))
    assert resp.status_code == 404


def test_sync_bank_403s_when_plaid_disabled_for_user(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    token, user_id = register_and_login("sync-plaid-disabled@example.com")
    bank = _make_bank(db, user_id)
    user = db.get(User, user_id)
    assert user is not None
    user.plaid_enabled = False
    db.commit()

    resp = client.post(f"/api/v1/banks/{bank.id}/sync", headers=_auth_headers(token))
    assert resp.status_code == 403


def test_sync_bank_404_for_another_users_bank(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    owner_token, owner_id = register_and_login("sync-owner@example.com")
    bank = _make_bank(db, owner_id)

    intruder_token, _intruder_id = register_and_login("sync-intruder@example.com")
    resp = client.post(f"/api/v1/banks/{bank.id}/sync", headers=_auth_headers(intruder_token))
    assert resp.status_code == 404


def test_list_banks_empty_for_new_user(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("no-banks@example.com")
    resp = client.get("/api/v1/banks", headers=_auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["data"] == []


def test_get_bank_404_for_nonexistent(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("bank-404@example.com")
    resp = client.get(f"/api/v1/banks/{uuid.uuid4()}", headers=_auth_headers(token))
    assert resp.status_code == 404


def test_list_banks_shows_health_and_zero_account_count(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    token, user_id = register_and_login("fresh-bank@example.com")
    _make_bank(db, user_id)

    resp = client.get("/api/v1/banks", headers=_auth_headers(token))
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["health"] == "healthy"
    # Link succeeded but no sync has run yet — zero accounts is a valid state (ROADMAP 7.1).
    assert data[0]["account_count"] == 0
    assert data[0]["last_synced_at"] is None


def test_a_second_users_token_cannot_see_the_first_users_bank(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    owner_token, owner_id = register_and_login("bank-owner-2@example.com")
    bank = _make_bank(db, owner_id)

    intruder_token, _intruder_id = register_and_login("bank-intruder@example.com")
    intruder_headers = _auth_headers(intruder_token)

    assert client.get(f"/api/v1/banks/{bank.id}", headers=intruder_headers).status_code == 404
    assert client.get("/api/v1/banks", headers=intruder_headers).json()["data"] == []
