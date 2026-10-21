import uuid
from datetime import datetime

from pydantic import BaseModel

from app.banks.models import Bank, PlaidItem


class BankPublic(BaseModel):
    """Bank + the subset of its PlaidItem fields safe to expose — access_token/cursor/item_id
    never leave the backend (API_SPEC.md §3)."""

    id: uuid.UUID
    institution_id: str
    institution_name: str
    health: str
    last_synced_at: datetime | None
    account_count: int
    created_at: datetime

    @classmethod
    def from_bank(cls, bank: Bank, item: PlaidItem, account_count: int) -> "BankPublic":
        return cls(
            id=bank.id,
            institution_id=item.institution_id,
            institution_name=item.institution_name,
            health=bank.health,
            last_synced_at=bank.last_synced_at,
            account_count=account_count,
            created_at=bank.created_at,
        )


class BankSyncResponse(BaseModel):
    job_id: uuid.UUID
