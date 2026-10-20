import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CategoryCreateRequest(BaseModel):
    primary_category: str = Field(min_length=1)
    detailed_category: str | None = None
    icon: str | None = None
    color: str | None = None


class CategoryUpdateRequest(BaseModel):
    primary_category: str | None = Field(default=None, min_length=1)
    detailed_category: str | None = None
    icon: str | None = None
    color: str | None = None


class CategoryPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID | None
    primary_category: str
    detailed_category: str | None
    icon: str | None
    color: str | None
    created_at: datetime
    updated_at: datetime
