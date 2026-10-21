import uuid
from datetime import datetime

from pydantic import BaseModel


class LinkTokenResponse(BaseModel):
    link_token: str
    expiration: datetime


class LinkTokenUpdateRequest(BaseModel):
    bank_id: uuid.UUID


class ExchangeTokenRequest(BaseModel):
    public_token: str
