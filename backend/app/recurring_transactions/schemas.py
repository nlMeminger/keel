import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.recurring_transactions.models import RecurringTransaction

Frequency = Literal["weekly", "monthly", "quarterly", "yearly"]


class RecurringTransactionCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    amount_expected: Decimal = Field(gt=0)
    frequency: Frequency
    account_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    merchant_id: uuid.UUID | None = None
    next_due_date: date | None = None
    is_bill: bool = False


class RecurringTransactionUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    amount_expected: Decimal | None = Field(default=None, gt=0)
    frequency: Frequency | None = None
    account_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    merchant_id: uuid.UUID | None = None
    next_due_date: date | None = None
    is_bill: bool | None = None


class RecurringTransactionPaymentCreateRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    date: date


class RecurringTransactionPublic(BaseModel):
    id: uuid.UUID
    name: str
    amount_expected: Decimal
    frequency: str
    account_id: uuid.UUID | None
    category_id: uuid.UUID | None
    merchant_id: uuid.UUID | None
    next_due_date: date | None
    last_paid_date: date | None
    is_bill: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_recurring(cls, row: RecurringTransaction) -> "RecurringTransactionPublic":
        return cls(
            id=row.id,
            name=row.name,
            amount_expected=row.amount_expected,
            frequency=row.frequency,
            account_id=row.account_id,
            category_id=row.category_id,
            merchant_id=row.merchant_id,
            next_due_date=row.next_due_date,
            last_paid_date=row.last_paid_date,
            is_bill=row.is_bill,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
