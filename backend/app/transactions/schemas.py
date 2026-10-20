import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TransferStatus = Literal["none", "suggested", "confirmed", "rejected"]
ConfirmOrReject = Literal["confirmed", "rejected"]
SortOption = Literal["date_asc", "date_desc", "amount_asc", "amount_desc"]


class TransactionCreateRequest(BaseModel):
    account_id: uuid.UUID
    category_id: uuid.UUID | None = None
    merchant_id: uuid.UUID | None = None
    amount: Decimal
    description: str = Field(min_length=1)
    notes: str | None = None
    date: date
    pending: bool = False


class TransactionUpdateRequest(BaseModel):
    """category_id/merchant_id/notes are all cleared-to-null-vs-omitted via `exclude_unset`
    in the router, not a plain `is not None` check — a client explicitly uncategorizing a
    transaction must be distinguishable from one that simply didn't touch the field."""

    category_id: uuid.UUID | None = None
    merchant_id: uuid.UUID | None = None
    notes: str | None = None
    # Only ever "confirmed"/"rejected" — the client resolves a suggestion, it never sets
    # "suggested"/"none" directly (those are detection's own job).
    transfer_status: ConfirmOrReject | None = None


class TransactionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    category_id: uuid.UUID | None
    merchant_id: uuid.UUID | None
    amount: Decimal
    description: str
    notes: str | None
    date: date
    pending: bool
    is_transfer: bool
    paired_transaction_id: uuid.UUID | None
    transfer_status: str
    created_at: datetime
    updated_at: datetime
