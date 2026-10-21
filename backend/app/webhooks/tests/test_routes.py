"""Router-level checks for POST /webhooks/plaid (ROADMAP 7.8). The positive case signs with
a local test keypair (see test_verification.py's module docstring for why — no public
ingress in this environment to receive a genuinely Plaid-signed webhook) but otherwise runs
the full real request pipeline: header parsing, verification, JSON parsing, and processing."""

import base64
import hashlib
import json
import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

from app.auth.models import User
from app.banks.models import Bank, PlaidItem
from app.jobs.models import Job
from app.webhooks import verification

KID = "test-kid-route"


def _b64url(value: int) -> str:
    return base64.urlsafe_b64encode(value.to_bytes(32, "big")).rstrip(b"=").decode()


@pytest.fixture(autouse=True)
def _clear_jwk_cache() -> None:
    verification._jwk_cache.clear()


def _make_bank(db: OrmSession, owner_id: uuid.UUID) -> Bank:
    item = PlaidItem(
        access_token="irrelevant",
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


def _make_user(db: OrmSession) -> User:
    user = User(email="webhook-route@example.com", password_hash="hashed", name="Tester")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_missing_verification_header_is_rejected_before_any_processing(
    client: TestClient, db: OrmSession
) -> None:
    user = _make_user(db)
    bank = _make_bank(db, user.id)
    item = db.get(PlaidItem, bank.plaid_item_id)
    assert item is not None

    jobs_before = db.query(Job).count()
    response = client.post(
        "/api/v1/webhooks/plaid",
        json={
            "webhook_type": "TRANSACTIONS",
            "webhook_code": "SYNC_UPDATES_AVAILABLE",
            "item_id": item.item_id,
        },
    )

    assert response.status_code == 401
    # "Rejected before any processing" — no job was created for the real linked bank.
    assert db.query(Job).count() == jobs_before


def test_invalid_signature_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/webhooks/plaid",
        content=b'{"webhook_type": "ITEM"}',
        headers={"Plaid-Verification": "garbage", "Content-Type": "application/json"},
    )
    assert response.status_code == 401


def test_validly_signed_webhook_triggers_health_update(
    client: TestClient, db: OrmSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The positive "triggers the expected side effect" case (ROADMAP 7.8) — uses an ITEM
    health-flip side effect rather than a transaction sync, since the latter would make a
    real Plaid call this fixture bank's fake access_token can't actually authenticate (that
    full real-bank path is covered in test_sandbox_integration.py instead)."""
    user = _make_user(db)
    bank = _make_bank(db, user.id)
    item = db.get(PlaidItem, bank.plaid_item_id)
    assert item is not None

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
            "webhook_type": "ITEM",
            "webhook_code": "ERROR",
            "item_id": item.item_id,
            "error": {"error_code": "ITEM_LOGIN_REQUIRED"},
        }
    ).encode()
    token = jwt.encode(
        {"iat": int(time.time()), "request_body_sha256": hashlib.sha256(body).hexdigest()},
        private_key,
        algorithm="ES256",
        headers={"kid": KID},
    )

    response = client.post(
        "/api/v1/webhooks/plaid",
        content=body,
        headers={"Plaid-Verification": token, "Content-Type": "application/json"},
    )

    assert response.status_code == 200
    result = response.json()["data"]
    assert result["status"] == "health_updated"
    assert result["health"] == "needs_reauth"
    db.refresh(bank)
    assert bank.health == "needs_reauth"
