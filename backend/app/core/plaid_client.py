import json
import uuid
from datetime import UTC, datetime

import plaid
from plaid.api import plaid_api
from plaid.exceptions import ApiException
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.auth.models import User
from app.banks.models import PlaidAPICall
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


def calls_this_month(db: DbSession, user_id: uuid.UUID) -> int:
    """Live count, never a separately-maintained counter (API_SPEC.md §18) — the same
    PlaidAPICall rows `/admin/plaid/api-stats` aggregates, scoped to the current calendar
    month in UTC."""
    month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    stmt = (
        select(func.count())
        .select_from(PlaidAPICall)
        .where(PlaidAPICall.user_id == user_id, PlaidAPICall.created_at >= month_start)
    )
    return db.scalar(stmt) or 0


def ensure_plaid_enabled(db: DbSession, user: User) -> None:
    """Every Plaid-calling code path must check this before the call, not after (CLAUDE.md
    Don't-do-this) — an admin-disabled or over-limit user gets a clean 403/429 instead of a
    call that bypasses the control."""
    if not user.plaid_enabled:
        raise AppError(403, "plaid_disabled", "Plaid access is disabled for this account.")
    if user.plaid_monthly_call_limit is not None:
        if calls_this_month(db, user.id) >= user.plaid_monthly_call_limit:
            raise AppError(429, "plaid_call_limit_reached", "Monthly Plaid call limit reached.")


def plaid_error_body(exc: ApiException) -> dict[str, str]:
    """Parses a raw Plaid ApiException's body JSON — shared by plaid_error_to_app_error and
    the ghost-item reconciliation sweep (7.11), which only needs the error_code, not a full
    AppError, since there's no request to respond to."""
    if not exc.body:
        return {}
    try:
        return dict(json.loads(exc.body))
    except ValueError:
        return {}


def plaid_error_to_app_error(exc: ApiException) -> AppError:
    """Translates a raw Plaid ApiException into the app's {error:{code,message}} envelope.
    ITEM_LOGIN_REQUIRED surfaces as 409 so the frontend can prompt reauth; anything else is a
    502 — an upstream failure, not something the caller did wrong."""
    payload = plaid_error_body(exc)
    error_code = payload.get("error_code", "plaid_error")
    message = payload.get("error_message", "Plaid request failed.")
    if error_code == "ITEM_LOGIN_REQUIRED":
        return AppError(409, "item_login_required", message)
    return AppError(502, "plaid_error", message)
