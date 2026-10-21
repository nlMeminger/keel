"""Confirms the real Plaid-calling half of webhook verification (ROADMAP 7.8) actually
reaches Plaid's API with real credentials. There's no way to obtain a genuinely valid kid
without a real webhook delivery (this environment has no public ingress — see
test_verification.py's docstring), so this only proves connectivity/credentials for
/webhook_verification_key/get, not a full positive signature-verification round trip
against Plaid's real key (that's covered, with a local test keypair, in test_verification.py
and test_routes.py)."""

import hashlib
import json
import time
import uuid
from collections.abc import Callable

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from plaid.model.products import Products
from plaid.model.sandbox_public_token_create_request import SandboxPublicTokenCreateRequest
from sqlalchemy.orm import Session as OrmSession

from app.banks.models import Bank, PlaidItem
from app.config import settings
from app.core.errors import AppError
from app.core.plaid_client import get_plaid_client
from app.jobs.models import Job
from app.webhooks import verification
from app.webhooks.tests.test_verification import _b64url
from app.webhooks.verification import _fetch_verification_key, _jwk_cache

SANDBOX_INSTITUTION_ID = "ins_109508"
KID = "test-kid-webhook-sandbox"

requires_sandbox = pytest.mark.skipif(
    not settings.plaid_client_id or not settings.plaid_secret,
    reason="Real Plaid sandbox credentials (PLAID_CLIENT_ID/PLAID_SECRET) are not configured.",
)


@requires_sandbox
def test_fetching_an_unknown_key_id_from_real_plaid_errors_cleanly() -> None:
    _jwk_cache.clear()
    with pytest.raises(AppError) as exc_info:
        _fetch_verification_key("not-a-real-key-id")
    assert exc_info.value.status_code == 401


@requires_sandbox
def test_webhook_for_a_real_linked_bank_enqueues_and_completes_a_real_sync(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The one path that needs a genuinely working access_token behind it: a webhook for a
    bank that's really linked in sandbox, enqueueing a sync that actually has to succeed
    against Plaid. The webhook's own signature is still a local test keypair (no public
    ingress to receive Plaid's real one — see test_verification.py), but everything after
    verification — item lookup, job creation, and the sync the job runs — is real."""
    _jwk_cache.clear()
    token, _user_id = register_and_login("webhook-sandbox@example.com")
    plaid_client = get_plaid_client()
    public_token = plaid_client.sandbox_public_token_create(
        SandboxPublicTokenCreateRequest(
            institution_id=SANDBOX_INSTITUTION_ID, initial_products=[Products("transactions")]
        )
    ).public_token
    bank_data = client.post(
        "/api/v1/plaid/exchange-token",
        headers={"Authorization": f"Bearer {token}"},
        json={"public_token": public_token},
    ).json()["data"]

    bank = db.get(Bank, uuid.UUID(bank_data["id"]))
    assert bank is not None
    real_item = db.get(PlaidItem, bank.plaid_item_id)
    assert real_item is not None

    private_key = ec.generate_private_key(ec.SECP256R1())
    numbers = private_key.public_key().public_numbers()
    jwk = {
        "kty": "EC",
        "crv": "P-256",
        "kid": KID,
        "x": _b64url(numbers.x),
        "y": _b64url(numbers.y),
    }
    monkeypatch.setattr(verification, "_fetch_verification_key", lambda key_id: jwk)

    body = json.dumps(
        {
            "webhook_type": "TRANSACTIONS",
            "webhook_code": "SYNC_UPDATES_AVAILABLE",
            "item_id": real_item.item_id,
        }
    ).encode()
    signed = jwt.encode(
        {"iat": int(time.time()), "request_body_sha256": hashlib.sha256(body).hexdigest()},
        private_key,
        algorithm="ES256",
        headers={"kid": KID},
    )

    response = client.post(
        "/api/v1/webhooks/plaid",
        content=body,
        headers={"Plaid-Verification": signed, "Content-Type": "application/json"},
    )

    assert response.status_code == 200
    result = response.json()["data"]
    assert result["status"] == "sync_enqueued"
    job = db.get(Job, uuid.UUID(result["job_id"]))
    assert job is not None
    assert job.status == "succeeded"
