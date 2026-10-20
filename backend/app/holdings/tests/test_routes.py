import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.accounts.models import Account


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_investment_account(client: TestClient, token: str) -> str:
    resp = client.post(
        "/api/v1/accounts",
        json={"name": "Brokerage", "account_type": "investment", "balance": "0"},
        headers=_auth_headers(token),
    )
    return str(resp.json()["data"]["id"])


def test_create_manual_holding_on_investment_account(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("holding-creator@example.com")
    account_id = _create_investment_account(client, token)

    resp = client.post(
        f"/api/v1/accounts/{account_id}/holdings",
        json={
            "symbol": "VTI",
            "name": "Vanguard Total Stock",
            "quantity": "10.5",
            "cost_basis": "2000.00",
        },
        headers=_auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["source"] == "manual"
    assert data["current_value"] is None

    list_resp = client.get(f"/api/v1/accounts/{account_id}/holdings", headers=_auth_headers(token))
    assert len(list_resp.json()["data"]) == 1


def test_create_holding_on_non_investment_account_rejected(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("holding-wrong-type@example.com")
    account_resp = client.post(
        "/api/v1/accounts",
        json={"name": "Checking", "account_type": "checking", "balance": "0"},
        headers=_auth_headers(token),
    )
    account_id = account_resp.json()["data"]["id"]

    resp = client.post(
        f"/api/v1/accounts/{account_id}/holdings",
        json={"symbol": "VTI", "name": "x", "quantity": "1", "cost_basis": "1"},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 422


def test_create_holding_on_plaid_linked_account_returns_403(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]], db: DbSession
) -> None:
    token, _user_id = register_and_login("holding-plaid-account@example.com")
    account_id = _create_investment_account(client, token)
    # Simulate Phase 7's real link-time flag flip (no live Plaid code path exists yet).
    account = db.scalar(select(Account).where(Account.id == uuid.UUID(account_id)))
    assert account is not None
    account.is_plaid_linked = True
    db.commit()

    resp = client.post(
        f"/api/v1/accounts/{account_id}/holdings",
        json={"symbol": "VTI", "name": "x", "quantity": "1", "cost_basis": "1"},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 403


def test_update_and_delete_plaid_sourced_holding_returns_403(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]], db: DbSession
) -> None:
    from app.holdings.models import Holding

    token, _user_id = register_and_login("holding-plaid-sourced@example.com")
    account_id = _create_investment_account(client, token)
    holding = Holding(
        account_id=uuid.UUID(account_id),
        symbol="AAPL",
        name="Apple",
        quantity=5,
        cost_basis=100,
        source="plaid",
    )
    db.add(holding)
    db.commit()
    db.refresh(holding)

    patch_resp = client.patch(
        f"/api/v1/accounts/{account_id}/holdings/{holding.id}",
        json={"quantity": "10"},
        headers=_auth_headers(token),
    )
    assert patch_resp.status_code == 403

    delete_resp = client.delete(
        f"/api/v1/accounts/{account_id}/holdings/{holding.id}", headers=_auth_headers(token)
    )
    assert delete_resp.status_code == 403


def test_update_manual_holding(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("holding-updater@example.com")
    account_id = _create_investment_account(client, token)
    create_resp = client.post(
        f"/api/v1/accounts/{account_id}/holdings",
        json={"symbol": "VTI", "name": "x", "quantity": "1", "cost_basis": "1"},
        headers=_auth_headers(token),
    )
    holding_id = create_resp.json()["data"]["id"]

    patch_resp = client.patch(
        f"/api/v1/accounts/{account_id}/holdings/{holding_id}",
        json={"current_value": "123.45"},
        headers=_auth_headers(token),
    )
    assert patch_resp.json()["data"]["current_value"] == "123.45"


def test_delete_manual_holding(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("holding-deleter@example.com")
    account_id = _create_investment_account(client, token)
    create_resp = client.post(
        f"/api/v1/accounts/{account_id}/holdings",
        json={"symbol": "VTI", "name": "x", "quantity": "1", "cost_basis": "1"},
        headers=_auth_headers(token),
    )
    holding_id = create_resp.json()["data"]["id"]

    assert (
        client.delete(
            f"/api/v1/accounts/{account_id}/holdings/{holding_id}", headers=_auth_headers(token)
        ).status_code
        == 204
    )
    list_resp = client.get(f"/api/v1/accounts/{account_id}/holdings", headers=_auth_headers(token))
    assert list_resp.json()["data"] == []


def test_holdings_require_auth(client: TestClient) -> None:
    assert client.get(f"/api/v1/accounts/{uuid.uuid4()}/holdings").status_code == 401


def test_holdings_on_nonexistent_account_returns_404(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("holding-nobody@example.com")
    resp = client.get(f"/api/v1/accounts/{uuid.uuid4()}/holdings", headers=_auth_headers(token))
    assert resp.status_code == 404


def test_a_second_users_token_cannot_see_or_modify_the_first_users_holdings(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    owner_token, _owner_id = register_and_login("holding-owner@example.com")
    account_id = _create_investment_account(client, owner_token)
    create_resp = client.post(
        f"/api/v1/accounts/{account_id}/holdings",
        json={"symbol": "VTI", "name": "x", "quantity": "1", "cost_basis": "1"},
        headers=_auth_headers(owner_token),
    )
    holding_id = create_resp.json()["data"]["id"]

    intruder_token, _intruder_id = register_and_login("holding-intruder@example.com")
    intruder_headers = _auth_headers(intruder_token)

    assert (
        client.get(f"/api/v1/accounts/{account_id}/holdings", headers=intruder_headers).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/v1/accounts/{account_id}/holdings/{holding_id}",
            json={"quantity": "99"},
            headers=intruder_headers,
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/v1/accounts/{account_id}/holdings/{holding_id}", headers=intruder_headers
        ).status_code
        == 404
    )
