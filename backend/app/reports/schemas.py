import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class NetWorthHistoryPoint(BaseModel):
    date: date
    net_worth: Decimal


class CashFlowPoint(BaseModel):
    period_start: date
    period_end: date
    inflow: Decimal
    outflow: Decimal


class SpendingByCategoryRow(BaseModel):
    category_id: uuid.UUID | None
    category_name: str | None
    total: Decimal


class CreditCardUtilization(BaseModel):
    account_id: uuid.UUID
    name: str
    balance: Decimal
    credit_limit: Decimal
    utilization: Decimal


class CreditScoreHistoryPoint(BaseModel):
    date: date
    value: Decimal


class CreditHealthResponse(BaseModel):
    accounts: list[CreditCardUtilization]
    # None when the user has no credit_card accounts (nothing to divide by) — distinct from
    # a legitimate 0, so the frontend can tell "no data" from "no usage" apart.
    overall_utilization: Decimal | None
    credit_score_history: list[CreditScoreHistoryPoint]


class HoldingPerformance(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    symbol: str
    name: str
    quantity: Decimal
    cost_basis: Decimal
    current_value: Decimal | None
    gain_loss: Decimal | None
    source: str
