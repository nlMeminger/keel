"""Exercises §3/§4's Plaid-pull path against Plaid's real sandbox API (ROADMAP 7.3) — no
mocks. Skipped entirely when PLAID_CLIENT_ID/PLAID_SECRET aren't configured."""

import uuid
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from plaid.model.products import Products
from plaid.model.sandbox_public_token_create_request import SandboxPublicTokenCreateRequest

from app.config import settings
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
