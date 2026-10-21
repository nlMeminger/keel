from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.budgets.schemas import BudgetPublic
from app.transactions.schemas import TransactionPublic


class CreditScoreSummary(BaseModel):
    value: Decimal
    date: date
    # None when there's only one credit_score entry yet — nothing to compare against.
    trend: Literal["up", "down", "flat"] | None


class DashboardSummary(BaseModel):
    net_worth: Decimal
    net_worth_delta: Decimal
    this_month_inflow: Decimal
    this_month_outflow: Decimal
    recent_transactions: list[TransactionPublic]
    budgets: list[BudgetPublic]
    latest_credit_score: CreditScoreSummary | None
