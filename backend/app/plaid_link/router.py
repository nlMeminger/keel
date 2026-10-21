from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.auth.models import User
from app.banks.schemas import BankPublic
from app.core.envelope import Envelope
from app.database import get_db
from app.dependencies import get_current_user
from app.plaid_link import service
from app.plaid_link.schemas import ExchangeTokenRequest, LinkTokenResponse, LinkTokenUpdateRequest

router = APIRouter(prefix="/plaid", tags=["plaid-link"])


@router.post("/link-token", response_model=Envelope[LinkTokenResponse])
def create_link_token(user: User = Depends(get_current_user)) -> dict[str, LinkTokenResponse]:
    link_token, expiration = service.create_link_token_for_new_bank(user)
    return {"data": LinkTokenResponse(link_token=link_token, expiration=expiration)}


@router.post("/link-token/update", response_model=Envelope[LinkTokenResponse])
def create_link_token_update(
    body: LinkTokenUpdateRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, LinkTokenResponse]:
    link_token, expiration = service.create_link_token_for_reauth(db, user, body.bank_id)
    return {"data": LinkTokenResponse(link_token=link_token, expiration=expiration)}


@router.post("/exchange-token", response_model=Envelope[BankPublic])
def exchange_token(
    body: ExchangeTokenRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, BankPublic]:
    bank, item = service.exchange_public_token(db, user, body.public_token)
    return {"data": BankPublic.from_bank(bank, item)}
