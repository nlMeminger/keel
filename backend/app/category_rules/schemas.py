import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.category_rules.models import CategoryRule


class CategoryRuleCreateRequest(BaseModel):
    merchant_contains: str | None = None
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None
    account_id: uuid.UUID | None = None
    category_id: uuid.UUID
    priority: int = 100
    active: bool = True


class CategoryRuleUpdateRequest(BaseModel):
    merchant_contains: str | None = None
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None
    account_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    priority: int | None = None
    active: bool | None = None


class CategoryRuleConditions(BaseModel):
    """Shared shape for `/category-rules/test` — the same matching conditions a rule stores,
    without the bookkeeping fields (`priority`/`active`) that only matter once it's saved."""

    merchant_contains: str | None = None
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None
    account_id: uuid.UUID | None = None


class CategoryRulePublic(BaseModel):
    id: uuid.UUID
    merchant_contains: str | None
    amount_min: Decimal | None
    amount_max: Decimal | None
    account_id: uuid.UUID | None
    category_id: uuid.UUID
    priority: int
    active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_rule(cls, rule: CategoryRule) -> "CategoryRulePublic":
        return cls(
            id=rule.id,
            merchant_contains=rule.merchant_contains,
            amount_min=rule.amount_min,
            amount_max=rule.amount_max,
            account_id=rule.account_id,
            category_id=rule.category_id,
            priority=rule.priority,
            active=rule.active,
            created_at=rule.created_at,
            updated_at=rule.updated_at,
        )


class TransactionMatchPublic(BaseModel):
    """Minimal transaction shape returned by /test and /apply — enough to identify and
    display a match without pulling in the full TransactionPublic schema."""

    id: uuid.UUID
    description: str
    amount: Decimal
    date: date

    model_config = {"from_attributes": True}


class CategoryRuleTestResponse(BaseModel):
    matches: list[TransactionMatchPublic]


class CategoryRuleApplyResponse(BaseModel):
    job_id: uuid.UUID
