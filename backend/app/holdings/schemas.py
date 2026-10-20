import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class HoldingCreateRequest(BaseModel):
    symbol: str = Field(min_length=1)
    name: str = Field(min_length=1)
    quantity: Decimal
    cost_basis: Decimal


class HoldingUpdateRequest(BaseModel):
    symbol: str | None = Field(default=None, min_length=1)
    name: str | None = Field(default=None, min_length=1)
    quantity: Decimal | None = None
    cost_basis: Decimal | None = None
    current_value: Decimal | None = None


class HoldingPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    security_id: str | None
    symbol: str
    name: str
    quantity: Decimal
    cost_basis: Decimal
    current_value: Decimal | None
    source: str
    created_at: datetime
    updated_at: datetime
