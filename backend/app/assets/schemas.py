import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class AssetCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    asset_type: str = Field(min_length=1)
    current_value: Decimal


class AssetUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    asset_type: str | None = Field(default=None, min_length=1)
    current_value: Decimal | None = None


class AssetPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    asset_type: str
    current_value: Decimal
    created_at: datetime
    updated_at: datetime
