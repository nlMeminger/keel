"""Tests the Plaid-Verification JWT algorithm itself (API_SPEC.md §17) against a locally
generated ES256 keypair — Plaid's real signing key is only ever usable by Plaid, so the only
way to exercise "is a correctly-signed token accepted, is a tampered one rejected" without a
real webhook delivery (this dev environment has no public ingress) is to sign with a test
keypair and monkeypatch the key-fetch step that would otherwise call Plaid's
/webhook_verification_key/get. Every rejection path below is still testing this module's own
logic exactly as it runs in production — only the *source* of the public key is swapped."""

import base64
import hashlib
import json
import time
import types

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.core.errors import AppError
from app.webhooks import verification

KID = "test-kid-1"


def _b64url(value: int) -> str:
    return base64.urlsafe_b64encode(value.to_bytes(32, "big")).rstrip(b"=").decode()


@pytest.fixture
def keypair() -> tuple[ec.EllipticCurvePrivateKey, dict[str, str]]:
    private_key = ec.generate_private_key(ec.SECP256R1())
    numbers = private_key.public_key().public_numbers()
    jwk = {
        "kty": "EC",
        "crv": "P-256",
        "kid": KID,
        "x": _b64url(numbers.x),
        "y": _b64url(numbers.y),
    }
    return private_key, jwk


@pytest.fixture(autouse=True)
def _clear_jwk_cache() -> None:
    verification._jwk_cache.clear()


def _sign(private_key: ec.EllipticCurvePrivateKey, body: bytes, iat: float | None = None) -> str:
    payload = {
        "iat": int(iat if iat is not None else time.time()),
        "request_body_sha256": hashlib.sha256(body).hexdigest(),
    }
    return jwt.encode(payload, private_key, algorithm="ES256", headers={"kid": KID})


def test_valid_webhook_is_accepted(
    keypair: tuple[ec.EllipticCurvePrivateKey, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key, jwk = keypair
    monkeypatch.setattr(verification, "_fetch_verification_key", lambda key_id: jwk)
    body = json.dumps({"webhook_type": "ITEM", "webhook_code": "LOGIN_REPAIRED"}).encode()
    token = _sign(private_key, body)

    payload = verification.verify_webhook(token, body)
    assert payload["request_body_sha256"] == hashlib.sha256(body).hexdigest()


def test_missing_header_is_rejected() -> None:
    with pytest.raises(AppError) as exc_info:
        verification.verify_webhook(None, b"{}")
    assert exc_info.value.status_code == 401


def test_malformed_header_is_rejected() -> None:
    with pytest.raises(AppError) as exc_info:
        verification.verify_webhook("not-a-jwt", b"{}")
    assert exc_info.value.status_code == 401


def test_wrong_algorithm_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    # Signed with HS256 instead of ES256 — must be rejected on the alg check alone, before
    # ever attempting a key lookup.
    def _fail(key_id: str) -> dict[str, str]:
        raise AssertionError("must not fetch a key for a non-ES256 token")

    monkeypatch.setattr(verification, "_fetch_verification_key", _fail)
    body = b"{}"
    token = jwt.encode(
        {"iat": int(time.time()), "request_body_sha256": hashlib.sha256(body).hexdigest()},
        "some-shared-secret-that-is-at-least-32-bytes-long",
        algorithm="HS256",
    )

    with pytest.raises(AppError) as exc_info:
        verification.verify_webhook(token, body)
    assert exc_info.value.status_code == 401


def test_tampered_body_is_rejected(
    keypair: tuple[ec.EllipticCurvePrivateKey, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key, jwk = keypair
    monkeypatch.setattr(verification, "_fetch_verification_key", lambda key_id: jwk)
    signed_body = b'{"webhook_type": "ITEM"}'
    token = _sign(private_key, signed_body)

    with pytest.raises(AppError) as exc_info:
        verification.verify_webhook(token, b'{"webhook_type": "TRANSACTIONS"}')
    assert exc_info.value.status_code == 401


def test_stale_iat_is_rejected(
    keypair: tuple[ec.EllipticCurvePrivateKey, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key, jwk = keypair
    monkeypatch.setattr(verification, "_fetch_verification_key", lambda key_id: jwk)
    body = b"{}"
    token = _sign(private_key, body, iat=time.time() - 301)

    with pytest.raises(AppError) as exc_info:
        verification.verify_webhook(token, body)
    assert exc_info.value.status_code == 401


def test_future_iat_beyond_skew_is_rejected(
    keypair: tuple[ec.EllipticCurvePrivateKey, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key, jwk = keypair
    monkeypatch.setattr(verification, "_fetch_verification_key", lambda key_id: jwk)
    body = b"{}"
    token = _sign(private_key, body, iat=time.time() + 120)

    with pytest.raises(AppError) as exc_info:
        verification.verify_webhook(token, body)
    assert exc_info.value.status_code == 401


def test_signature_from_a_different_key_is_rejected(
    keypair: tuple[ec.EllipticCurvePrivateKey, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _real_private_key, jwk = keypair
    other_private_key = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(verification, "_fetch_verification_key", lambda key_id: jwk)
    body = b"{}"
    # Signed with a *different* private key than the one whose public half is in `jwk`.
    token = _sign(other_private_key, body)

    with pytest.raises(AppError) as exc_info:
        verification.verify_webhook(token, body)
    assert exc_info.value.status_code == 401


def test_verification_key_is_cached_by_kid(
    keypair: tuple[ec.EllipticCurvePrivateKey, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercises the real caching logic inside _fetch_verification_key (not a bypass of it)
    by substituting only the underlying Plaid client call beneath it."""
    private_key, jwk = keypair
    call_count = 0

    def webhook_verification_key_get(request: object) -> types.SimpleNamespace:
        nonlocal call_count
        call_count += 1
        key_obj = types.SimpleNamespace(to_dict=lambda: jwk)
        return types.SimpleNamespace(key=key_obj)

    fake_client = types.SimpleNamespace(webhook_verification_key_get=webhook_verification_key_get)
    monkeypatch.setattr(verification, "get_plaid_client", lambda: fake_client)
    body = b"{}"

    verification.verify_webhook(_sign(private_key, body), body)
    verification.verify_webhook(_sign(private_key, body), body)

    assert call_count == 1
