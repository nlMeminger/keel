"""Exercises §2 against Plaid's real sandbox API (ROADMAP 7.2) — no mocks. Requires real
PLAID_CLIENT_ID/PLAID_SECRET; skipped entirely when they're not configured (a fresh clone
with no Plaid account yet, per ROADMAP.md's D3) rather than faked with a mocked client."""

import uuid
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from plaid.model.products import Products
from plaid.model.sandbox_public_token_create_request import SandboxPublicTokenCreateRequest
from sqlalchemy.orm import Session as OrmSession

from app.banks.models import Bank, PlaidItem
from app.config import settings
from app.core.encryption import decrypt
from app.core.plaid_client import get_plaid_client

# First Platypus Bank — Plaid's own general-purpose sandbox institution, supports every
# product, authenticates with the standard user_good/pass_good sandbox credentials.
SANDBOX_INSTITUTION_ID = "ins_109508"

requires_sandbox = pytest.mark.skipif(
    not settings.plaid_client_id or not settings.plaid_secret,
    reason="Real Plaid sandbox credentials (PLAID_CLIENT_ID/PLAID_SECRET) are not configured.",
)


def _sandbox_public_token() -> str:
    """Bypasses the Link UI exactly the way Plaid's sandbox testing docs recommend for
    automated tests: /sandbox/public_token/create hands back a public_token for a given
    institution/test credentials without driving a browser through Link."""
    client = get_plaid_client()
    response = client.sandbox_public_token_create(
        SandboxPublicTokenCreateRequest(
            institution_id=SANDBOX_INSTITUTION_ID, initial_products=[Products("transactions")]
        )
    )
    return str(response.public_token)


@requires_sandbox
def test_link_token_create_against_real_sandbox(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("linker@example.com")

    response = client.post("/api/v1/plaid/link-token", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["link_token"].startswith("link-")


@requires_sandbox
def test_exchange_token_creates_bank_with_encrypted_access_token(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    token, user_id = register_and_login("exchanger@example.com")
    public_token = _sandbox_public_token()

    response = client.post(
        "/api/v1/plaid/exchange-token",
        headers={"Authorization": f"Bearer {token}"},
        json={"public_token": public_token},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["institution_name"]
    assert data["health"] == "healthy"

    bank = db.get(Bank, uuid.UUID(data["id"]))
    assert bank is not None
    assert bank.owner_id == user_id

    item = db.get(PlaidItem, bank.plaid_item_id)
    assert item is not None
    # The raw row must never hold the plaintext access_token (ROADMAP 7.7) — only the
    # decrypted value, which the app can still use to make a live Plaid call, does.
    assert not item.access_token.startswith("access-")
    decrypted = decrypt(item.access_token)
    assert decrypted.startswith("access-")

    live_client = get_plaid_client()
    from plaid.model.accounts_get_request import AccountsGetRequest

    accounts_response = live_client.accounts_get(AccountsGetRequest(access_token=decrypted))
    assert len(accounts_response.accounts) > 0


@requires_sandbox
def test_link_token_update_requires_owning_bank(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    owner_token, owner_id = register_and_login("bank-owner@example.com")
    other_token, _other_id = register_and_login("not-the-owner@example.com")

    exchange_response = client.post(
        "/api/v1/plaid/exchange-token",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"public_token": _sandbox_public_token()},
    )
    bank_id = exchange_response.json()["data"]["id"]

    other_users_attempt = client.post(
        "/api/v1/plaid/link-token/update",
        headers={"Authorization": f"Bearer {other_token}"},
        json={"bank_id": bank_id},
    )
    assert other_users_attempt.status_code == 404

    owners_attempt = client.post(
        "/api/v1/plaid/link-token/update",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"bank_id": bank_id},
    )
    assert owners_attempt.status_code == 200
    assert owners_attempt.json()["data"]["link_token"].startswith("link-")
