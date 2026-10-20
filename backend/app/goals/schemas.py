import datetime as dt
import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

from app.goals.models import SavingsGoal


class SavingsGoalCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    target_amount: Decimal = Field(gt=0)
    target_date: dt.date | None = None


class SavingsGoalUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    target_amount: Decimal | None = Field(default=None, gt=0)
    target_date: dt.date | None = None


class GoalContributionCreateRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    date: dt.date
    note: str | None = None


class SavingsGoalPublic(BaseModel):
    id: uuid.UUID
    name: str
    target_amount: Decimal
    target_date: dt.date | None
    progress_amount: Decimal
    created_at: dt.datetime
    updated_at: dt.datetime

    @classmethod
    def from_goal(cls, goal: SavingsGoal, progress_amount: Decimal) -> "SavingsGoalPublic":
        return cls(
            id=goal.id,
            name=goal.name,
            target_amount=goal.target_amount,
            target_date=goal.target_date,
            progress_amount=progress_amount,
            created_at=goal.created_at,
            updated_at=goal.updated_at,
        )
