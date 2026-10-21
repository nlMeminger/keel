import hashlib
import hmac
import time
from typing import Any

import jwt
from plaid.exceptions import ApiException
from plaid.model.webhook_verification_key_get_request import WebhookVerificationKeyGetRequest

from app.core.errors import AppError
from app.core.plaid_client import get_plaid_client

# Plaid's own guidance: reject a webhook more than 5 minutes old (replay protection). A
# small forward-skew allowance covers minor clock drift between servers.
MAX_WEBHOOK_AGE_SECONDS = 300
MAX_CLOCK_SKEW_SECONDS = 60

_jwk_cache: dict[str, dict[str, Any]] = {}


def _fetch_verification_key(key_id: str) -> dict[str, Any]:
    """Fetches and caches a Plaid webhook signing key by kid (API_SPEC.md §17) — re-fetched
    only when a new kid is seen (key rotation), per Plaid's own caching guidance. Not routed
    through banks_service.call_plaid: this call isn't made on any particular user's behalf,
    it's infra-level verification plumbing, not something /admin/plaid/api-stats should
    attribute to a user."""
    cached = _jwk_cache.get(key_id)
    if cached is not None:
        return cached

    client = get_plaid_client()
    try:
        response = client.webhook_verification_key_get(
            WebhookVerificationKeyGetRequest(key_id=key_id)
        )
    except ApiException as exc:
        raise AppError(401, "invalid_webhook", "Could not verify webhook signature.") from exc

    key: dict[str, Any] = response.key.to_dict()
    if key.get("expired_at") is not None:
        raise AppError(401, "invalid_webhook", "Webhook signing key has expired.")
    _jwk_cache[key_id] = key
    return key


def verify_webhook(verification_header: str | None, raw_body: bytes) -> dict[str, Any]:
    """Verifies a Plaid-Verification JWT (API_SPEC.md §17) — rejects before any webhook
    processing on a missing header, wrong algorithm, invalid signature, mismatched body
    hash, or a stale `iat`. Returns the JWT's own payload (`iat`/`request_body_sha256`) —
    the webhook's actual data is the raw request body itself, parsed separately once this
    passes."""
    if not verification_header:
        raise AppError(401, "invalid_webhook", "Missing Plaid-Verification header.")

    try:
        unverified_header = jwt.get_unverified_header(verification_header)
    except jwt.InvalidTokenError as exc:
        raise AppError(401, "invalid_webhook", "Malformed verification header.") from exc

    if unverified_header.get("alg") != "ES256":
        raise AppError(401, "invalid_webhook", "Unexpected signing algorithm.")
    key_id = unverified_header.get("kid")
    if not key_id:
        raise AppError(401, "invalid_webhook", "Missing key id.")

    jwk_dict = _fetch_verification_key(key_id)
    try:
        signing_key = jwt.PyJWK(jwk_dict, algorithm="ES256")
        payload: dict[str, Any] = jwt.decode(
            verification_header, key=signing_key.key, algorithms=["ES256"]
        )
    except jwt.InvalidTokenError as exc:
        raise AppError(401, "invalid_webhook", "Invalid webhook signature.") from exc

    issued_at = payload.get("iat")
    if not isinstance(issued_at, int | float):
        raise AppError(401, "invalid_webhook", "Missing iat claim.")
    now = time.time()
    if now - issued_at > MAX_WEBHOOK_AGE_SECONDS or issued_at - now > MAX_CLOCK_SKEW_SECONDS:
        raise AppError(401, "invalid_webhook", "Webhook timestamp is stale or invalid.")

    expected_hash = payload.get("request_body_sha256")
    if not isinstance(expected_hash, str):
        raise AppError(401, "invalid_webhook", "Missing request_body_sha256 claim.")
    actual_hash = hashlib.sha256(raw_body).hexdigest()
    if not hmac.compare_digest(expected_hash, actual_hash):
        raise AppError(401, "invalid_webhook", "Webhook body hash mismatch.")

    return payload
