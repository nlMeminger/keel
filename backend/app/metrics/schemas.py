import datetime as dt
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MetricCreateRequest(BaseModel):
    type: str = Field(min_length=1)
    value: Decimal
    date: dt.date
    note: str | None = None
    account_id: uuid.UUID | None = None
    asset_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _validate_exclusive(self) -> "MetricCreateRequest":
        if self.account_id is not None and self.asset_id is not None:
            raise ValueError("account_id and asset_id are mutually exclusive.")
        return self


class MetricBulkCreateRequest(BaseModel):
    entries: list[MetricCreateRequest] = Field(min_length=1)


class MetricUpdateRequest(BaseModel):
    """Corrects a past entry (API_SPEC.md §14) — account_id/asset_id aren't editable here;
    delete and re-create if a metric was logged against the wrong account/asset."""

    type: str | None = Field(default=None, min_length=1)
    value: Decimal | None = None
    date: dt.date | None = None
    note: str | None = None


class MetricPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    value: Decimal
    date: dt.date
    note: str | None
    account_id: uuid.UUID | None
    asset_id: uuid.UUID | None
    created_at: dt.datetime
    updated_at: dt.datetime
