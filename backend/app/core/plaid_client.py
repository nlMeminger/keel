import json

import plaid
from plaid.api import plaid_api
from plaid.exceptions import ApiException

from app.auth.models import User
from app.config import settings
from app.core.errors import AppError

_ENVIRONMENTS = {
    "sandbox": plaid.Environment.Sandbox,
    "production": plaid.Environment.Production,
}


def get_plaid_client() -> plaid_api.PlaidApi:
    """Configured Plaid API client for settings.plaid_env. client_id/secret are sent as
    headers by the generated client itself (Configuration.api_key), never in request bodies."""
    configuration = plaid.Configuration(
        host=_ENVIRONMENTS[settings.plaid_env],
        api_key={"clientId": settings.plaid_client_id, "secret": settings.plaid_secret},
    )
    return plaid_api.PlaidApi(plaid.ApiClient(configuration))


def ensure_plaid_enabled(user: User) -> None:
    """Every Plaid-calling code path must check this before the call, not after (CLAUDE.md
    Don't-do-this) — an admin-disabled user gets a clean 403 instead of a call that bypasses
    the control. monthly_call_limit enforcement joins this once PlaidAPICall exists (7.6) to
    count calls against; `plaid_enabled` alone needs nothing further and is checked now."""
    if not user.plaid_enabled:
        raise AppError(403, "plaid_disabled", "Plaid access is disabled for this account.")


def plaid_error_to_app_error(exc: ApiException) -> AppError:
    """Translates a raw Plaid ApiException into the app's {error:{code,message}} envelope.
    ITEM_LOGIN_REQUIRED surfaces as 409 so the frontend can prompt reauth; anything else is a
    502 — an upstream failure, not something the caller did wrong."""
    payload: dict[str, str] = {}
    if exc.body:
        try:
            payload = json.loads(exc.body)
        except ValueError:
            payload = {}
    error_code = payload.get("error_code", "plaid_error")
    message = payload.get("error_message", "Plaid request failed.")
    if error_code == "ITEM_LOGIN_REQUIRED":
        return AppError(409, "item_login_required", message)
    return AppError(502, "plaid_error", message)
