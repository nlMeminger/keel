import datetime as dt
import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

from app.budgets.models import Budget


class BudgetCreateRequest(BaseModel):
    category_id: uuid.UUID | None = None
    amount_limit: Decimal = Field(gt=0)
    start_date: dt.date


class BudgetUpdateRequest(BaseModel):
    """category_id uses exclude_unset in the router so an explicit null (switch to an
    overall budget) is distinguishable from an omitted field (leave scope untouched)."""

    category_id: uuid.UUID | None = None
    amount_limit: Decimal | None = Field(default=None, gt=0)
    start_date: dt.date | None = None


class BudgetPublic(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID | None
    amount_limit: Decimal
    period: str
    start_date: dt.date
    spend_so_far: Decimal
    created_at: dt.datetime
    updated_at: dt.datetime

    @classmethod
    def from_budget(cls, budget: Budget, spend_so_far: Decimal) -> "BudgetPublic":
        return cls(
            id=budget.id,
            category_id=budget.category_id,
            amount_limit=budget.amount_limit,
            period=budget.period,
            start_date=budget.start_date,
            spend_so_far=spend_so_far,
            created_at=budget.created_at,
            updated_at=budget.updated_at,
        )
