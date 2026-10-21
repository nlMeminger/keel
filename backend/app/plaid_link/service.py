import uuid
from datetime import datetime

from plaid.model.country_code import CountryCode
from plaid.model.institutions_get_by_id_request import InstitutionsGetByIdRequest
from plaid.model.item_get_request import ItemGetRequest
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_update import LinkTokenCreateRequestUpdate
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.user_create_request import UserCreateRequest
from sqlalchemy.orm import Session as DbSession

from app.auth.models import User
from app.banks import service as banks_service
from app.banks.models import Bank, PlaidItem
from app.config import settings
from app.core.encryption import decrypt
from app.core.errors import AppError
from app.core.plaid_client import ensure_plaid_enabled, get_plaid_client

CLIENT_NAME = "Keel"
LANGUAGE = "en"
COUNTRY_CODES = [CountryCode("US")]
PRODUCTS = [Products("transactions")]
# Only enabled when the linked institution actually supports it — never blocks Item creation
# the way a plain `products` entry would for an institution that doesn't.
REQUIRED_IF_SUPPORTED_PRODUCTS = [Products("investments")]


def _webhook_kwargs() -> dict[str, str]:
    return {"webhook": settings.plaid_webhook_url} if settings.plaid_webhook_url else {}


def create_link_token_for_new_bank(db: DbSession, user: User) -> tuple[str, datetime]:
    """POST /plaid/link-token (API_SPEC.md §2) — a fresh Link token for adding a new bank."""
    ensure_plaid_enabled(user)
    client = get_plaid_client()
    request = LinkTokenCreateRequest(
        client_name=CLIENT_NAME,
        language=LANGUAGE,
        country_codes=COUNTRY_CODES,
        user=LinkTokenCreateRequestUser(client_user_id=str(user.id)),
        products=PRODUCTS,
        required_if_supported_products=REQUIRED_IF_SUPPORTED_PRODUCTS,
        **_webhook_kwargs(),
    )
    response = banks_service.call_plaid(
        db, user.id, "link_token_create", lambda: client.link_token_create(request)
    )
    return response.link_token, response.expiration


def create_link_token_for_reauth(
    db: DbSession, user: User, bank_id: uuid.UUID
) -> tuple[str, datetime]:
    """POST /plaid/link-token/update (API_SPEC.md §2) — update-mode Link token for a bank
    needing reauth. No `products` here, per Plaid's update-mode guidance: update mode repairs
    the existing Item's credentials, it never changes which products the Item supports.

    Update-mode requests additionally require a Plaid-side `user_id` (Plaid now enforces this
    for every update-mode request, not just consumer-report-style products) — /user/create is
    idempotent per client_user_id, so this never creates a duplicate Plaid User on repeat calls.
    """
    ensure_plaid_enabled(user)
    _, item = banks_service.get_bank_with_item(db, user, bank_id)
    client = get_plaid_client()
    plaid_user_id = banks_service.call_plaid(
        db,
        user.id,
        "user_create",
        lambda: client.user_create(UserCreateRequest(client_user_id=str(user.id))).user_id,
    )
    request = LinkTokenCreateRequest(
        client_name=CLIENT_NAME,
        language=LANGUAGE,
        country_codes=COUNTRY_CODES,
        user=LinkTokenCreateRequestUser(client_user_id=str(user.id)),
        user_id=plaid_user_id,
        access_token=decrypt(item.access_token),
        update=LinkTokenCreateRequestUpdate(user=True),
        **_webhook_kwargs(),
    )
    response = banks_service.call_plaid(
        db, user.id, "link_token_create", lambda: client.link_token_create(request)
    )
    return response.link_token, response.expiration


def exchange_public_token(db: DbSession, user: User, public_token: str) -> tuple[Bank, PlaidItem]:
    """POST /plaid/exchange-token (API_SPEC.md §2) — one-time exchange of Link's public_token
    for a real access_token, then creates the Bank/PlaidItem pair backing the rest of Phase 7.
    public_token is single-use; nothing here retries on failure."""
    ensure_plaid_enabled(user)
    client = get_plaid_client()
    exchange = banks_service.call_plaid(
        db,
        user.id,
        "item_public_token_exchange",
        lambda: client.item_public_token_exchange(
            ItemPublicTokenExchangeRequest(public_token=public_token)
        ),
    )
    item_info = banks_service.call_plaid(
        db,
        user.id,
        "item_get",
        lambda: client.item_get(ItemGetRequest(access_token=exchange.access_token)).item,
    )
    institution_id = item_info.institution_id
    if institution_id is None:
        raise AppError(502, "plaid_error", "Linked item has no associated institution.")
    institution = banks_service.call_plaid(
        db,
        user.id,
        "institutions_get_by_id",
        lambda: (
            client.institutions_get_by_id(
                InstitutionsGetByIdRequest(
                    institution_id=institution_id, country_codes=COUNTRY_CODES
                )
            ).institution
        ),
    )

    bank, created_item = banks_service.create_bank_from_exchange(
        db,
        user,
        access_token=exchange.access_token,
        item_id=exchange.item_id,
        institution_id=institution_id,
        institution_name=institution.name,
    )
    # A Bank can briefly exist with zero accounts (ROADMAP 7.1) — this closes that window
    # immediately rather than waiting for the first scheduled/manual sync.
    banks_service.pull_accounts_and_holdings(db, user, bank, created_item)
    return bank, created_item
