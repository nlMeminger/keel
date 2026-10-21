"""Exercises §3/§4's Plaid-pull path against Plaid's real sandbox API (ROADMAP 7.3) — no
mocks. Skipped entirely when PLAID_CLIENT_ID/PLAID_SECRET aren't configured."""

import uuid
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from plaid.exceptions import ApiException
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.products import Products
from plaid.model.sandbox_public_token_create_request import SandboxPublicTokenCreateRequest
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.banks.models import Bank, PlaidAPICall, PlaidItem
from app.config import settings
from app.core.encryption import decrypt
from app.core.plaid_client import get_plaid_client

# First Platypus Bank — supports every Plaid product, including depository/credit/loan/
# investment accounts all on one Item, so a single link exercises the whole type mapping.
SANDBOX_INSTITUTION_ID = "ins_109508"

requires_sandbox = pytest.mark.skipif(
    not settings.plaid_client_id or not settings.plaid_secret,
    reason="Real Plaid sandbox credentials (PLAID_CLIENT_ID/PLAID_SECRET) are not configured.",
)


def _link_sandbox_bank(client: TestClient, token: str) -> dict[str, object]:
    plaid_client = get_plaid_client()
    public_token = plaid_client.sandbox_public_token_create(
        SandboxPublicTokenCreateRequest(
            institution_id=SANDBOX_INSTITUTION_ID,
            initial_products=[Products("transactions"), Products("investments")],
        )
    ).public_token
    response = client.post(
        "/api/v1/plaid/exchange-token",
        headers={"Authorization": f"Bearer {token}"},
        json={"public_token": public_token},
    )
    assert response.status_code == 200
    result: dict[str, object] = response.json()["data"]
    return result


@requires_sandbox
def test_linking_a_sandbox_bank_pulls_accounts_alongside_manual_ones(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("full-link@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    client.post(
        "/api/v1/accounts",
        json={"name": "Manual checking", "account_type": "checking", "balance": "42.00"},
        headers=headers,
    )

    bank = _link_sandbox_bank(client, token)
    assert isinstance(bank["account_count"], int)
    assert bank["account_count"] > 0

    banks_list = client.get("/api/v1/banks", headers=headers).json()["data"]
    assert len(banks_list) == 1
    assert banks_list[0]["account_count"] == bank["account_count"]

    bank_accounts = client.get(
        "/api/v1/accounts", params={"bank_id": bank["id"]}, headers=headers
    ).json()["data"]
    assert len(bank_accounts) == bank["account_count"]
    assert all(a["is_plaid_linked"] for a in bank_accounts)
    assert all(a["bank_id"] == bank["id"] for a in bank_accounts)

    all_accounts = client.get("/api/v1/accounts", headers=headers).json()["data"]
    assert len(all_accounts) == len(bank_accounts) + 1
    assert any(a["name"] == "Manual checking" and not a["is_plaid_linked"] for a in all_accounts)

    account_types = {a["account_type"] for a in bank_accounts}
    assert "investment" in account_types
    assert "mortgage" in account_types
    assert "student_loan" in account_types


@requires_sandbox
def test_investment_account_holdings_populate_read_only(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("holdings-link@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    bank = _link_sandbox_bank(client, token)

    bank_accounts = client.get(
        "/api/v1/accounts", params={"bank_id": bank["id"]}, headers=headers
    ).json()["data"]
    investment_account = next(a for a in bank_accounts if a["account_type"] == "investment")

    holdings = client.get(
        f"/api/v1/accounts/{investment_account['id']}/holdings", headers=headers
    ).json()["data"]
    assert len(holdings) > 0
    assert all(h["source"] == "plaid" for h in holdings)

    # Plaid-sourced holdings are read-only, same as Phase 4 already enforces.
    forbidden = client.post(
        f"/api/v1/accounts/{investment_account['id']}/holdings",
        json={"symbol": "ACME", "name": "Acme Corp", "quantity": "1", "cost_basis": "1"},
        headers=headers,
    )
    assert forbidden.status_code == 403


@requires_sandbox
def test_linking_logs_one_plaid_api_call_row_per_real_call(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    token, user_id = register_and_login("call-log-link@example.com")
    _link_sandbox_bank(client, token)

    rows = db.scalars(select(PlaidAPICall).where(PlaidAPICall.user_id == user_id)).all()
    endpoints = {row.endpoint for row in rows}
    # One row per real call the app itself made — never for sandbox_public_token_create,
    # which only simulates what the user's browser does in Link, not an app-initiated call.
    assert {
        "item_public_token_exchange",
        "item_get",
        "institutions_get_by_id",
        "accounts_get",
        "investments_holdings_get",
    } <= endpoints
    assert all(row.status == "success" for row in rows)
    assert all(row.user_id == user_id for row in rows)


@requires_sandbox
def test_unlinking_a_real_bank_removes_it_from_plaid_and_deactivates_its_accounts(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    token, _user_id = register_and_login("unlink-sandbox@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    bank = _link_sandbox_bank(client, token)
    bank_accounts = client.get(
        "/api/v1/accounts", params={"bank_id": bank["id"]}, headers=headers
    ).json()["data"]
    assert len(bank_accounts) > 0

    bank_row = db.get(Bank, uuid.UUID(str(bank["id"])))
    assert bank_row is not None
    item_id = bank_row.plaid_item_id

    delete_resp = client.delete(f"/api/v1/banks/{bank['id']}", headers=headers)
    assert delete_resp.status_code == 204

    # Bank row is gone — unlinking isn't a soft-delete on Bank itself.
    assert client.get(f"/api/v1/banks/{bank['id']}", headers=headers).status_code == 404
    assert client.get("/api/v1/banks", headers=headers).json()["data"] == []

    # PlaidItem is retained with removed_at set — the ghost-item check (7.11) needs this row.
    item = db.get(PlaidItem, item_id)
    assert item is not None
    assert item.removed_at is not None

    # Plaid's side genuinely no longer has this item — a direct call with the (now-decrypted-
    # and-still-known-to-us-for-this-test) access_token must fail, not succeed.
    try:
        get_plaid_client().accounts_get(AccountsGetRequest(access_token=decrypt(item.access_token)))
        raise AssertionError("Plaid should no longer recognize a removed item's access_token")
    except ApiException as exc:
        assert exc.status == 400

    # Its accounts are deactivated and unlinked, not left as dangling Plaid-linked rows.
    for account in bank_accounts:
        current = client.get(f"/api/v1/accounts/{account['id']}", headers=headers).json()["data"]
        assert current["is_active"] is False
        assert current["bank_id"] is None
