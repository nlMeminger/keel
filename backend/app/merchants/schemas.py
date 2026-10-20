import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MerchantCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)


class MerchantUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    aliases: list[str] | None = None


class MerchantPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    aliases: list[str]
    created_at: datetime
    updated_at: datetime
