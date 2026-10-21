"""Exercises §16's transaction-sync path against Plaid's real sandbox API (ROADMAP 7.4) —
no mocks. Skipped entirely when PLAID_CLIENT_ID/PLAID_SECRET aren't configured."""

import uuid
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from plaid.model.products import Products
from plaid.model.sandbox_public_token_create_request import SandboxPublicTokenCreateRequest

from app.config import settings
from app.core.plaid_client import get_plaid_client

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
            initial_products=[Products("transactions")],
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
def test_bank_sync_pulls_real_transactions_with_sign_flipped(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("sync-flow@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    bank = _link_sandbox_bank(client, token)

    sync_resp = client.post(f"/api/v1/banks/{bank['id']}/sync", headers=headers)
    assert sync_resp.status_code == 202
    job_id = sync_resp.json()["data"]["job_id"]

    job_status = client.get(f"/api/v1/sync/jobs/{job_id}", headers=headers).json()["data"]
    assert job_status["status"] == "succeeded"

    bank_detail = client.get(f"/api/v1/banks/{bank['id']}", headers=headers).json()["data"]
    assert bank_detail["last_synced_at"] is not None

    transactions = client.get(
        "/api/v1/transactions", params={"page_size": 200}, headers=headers
    ).json()["data"]
    # Sandbox pre-populates real transaction history on every account for this institution.
    assert len(transactions) > 0
    # Every synced transaction lands on one of this bank's own accounts.
    bank_account_ids = {
        a["id"]
        for a in client.get(
            "/api/v1/accounts", params={"bank_id": bank["id"]}, headers=headers
        ).json()["data"]
    }
    assert {t["account_id"] for t in transactions} <= bank_account_ids

    # Plaid signs positive=outflow; this app signs positive=inflow (SPEC.md §5) — at least
    # one synced expense must have flipped to a negative amount, not passed through raw.
    assert any(Decimal(t["amount"]) < 0 for t in transactions)


@requires_sandbox
def test_sync_bank_is_idempotent_on_repeat_runs(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("sync-idempotent@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    bank = _link_sandbox_bank(client, token)

    params = {"page_size": 200}
    client.post(f"/api/v1/banks/{bank['id']}/sync", headers=headers)
    first_count = len(
        client.get("/api/v1/transactions", params=params, headers=headers).json()["data"]
    )

    # Running the same sync again must not duplicate anything already stored.
    client.post(f"/api/v1/banks/{bank['id']}/sync", headers=headers)
    second_count = len(
        client.get("/api/v1/transactions", params=params, headers=headers).json()["data"]
    )

    assert second_count == first_count
