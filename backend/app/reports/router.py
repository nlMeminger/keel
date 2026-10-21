from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DbSession

from app.auth.models import User
from app.core.envelope import single_page
from app.database import get_db
from app.dependencies import get_current_user
from app.reports import service
from app.reports.schemas import (
    CashFlowPoint,
    CreditCardUtilization,
    CreditHealthResponse,
    CreditScoreHistoryPoint,
    HoldingPerformance,
    NetWorthHistoryPoint,
    SpendingByCategoryRow,
)

router = APIRouter(prefix="/reports", tags=["reports"])

GranularityParam = Literal["day", "week", "month"]


def _this_month_start() -> date:
    return date.today().replace(day=1)


@router.get("/net-worth-history")
def net_worth_history(
    granularity: GranularityParam = Query(default="day"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    resolved_to = date_to or date.today()
    resolved_from = date_from or service.default_history_date_from(
        db, user, ("account_balance", "asset_value")
    )
    points = service.net_worth_history(db, user, granularity, resolved_from, resolved_to)
    return single_page(
        [NetWorthHistoryPoint(date=point_date, net_worth=value) for point_date, value in points]
    )


@router.get("/cash-flow")
def cash_flow(
    granularity: GranularityParam = Query(default="day"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    resolved_to = date_to or date.today()
    resolved_from = date_from or _this_month_start()
    rows = service.cash_flow(db, user, granularity, resolved_from, resolved_to)
    return single_page(
        [
            CashFlowPoint(period_start=start, period_end=end, inflow=inflow, outflow=outflow)
            for start, end, inflow, outflow in rows
        ]
    )


@router.get("/spending-by-category")
def spending_by_category(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    resolved_to = date_to or date.today()
    resolved_from = date_from or _this_month_start()
    rows = service.spending_by_category(db, user, resolved_from, resolved_to)
    return single_page(
        [
            SpendingByCategoryRow(category_id=category_id, category_name=category_name, total=total)
            for category_id, category_name, total in rows
        ]
    )


@router.get("/credit-health")
def credit_health(
    granularity: GranularityParam = Query(default="day"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, CreditHealthResponse]:
    resolved_to = date_to or date.today()
    resolved_from = date_from or service.default_history_date_from(db, user, ("credit_score",))

    accounts = service.credit_card_utilization(db, user)
    utilizations = [
        CreditCardUtilization(
            account_id=account.id,
            name=account.name,
            balance=account.balance,
            credit_limit=Decimal(str(account.detail["credit_limit"])),
            utilization=account.balance / Decimal(str(account.detail["credit_limit"])),
        )
        for account in accounts
    ]
    total_limit = sum((row.credit_limit for row in utilizations), Decimal("0"))
    overall = (
        sum((row.balance for row in utilizations), Decimal("0")) / total_limit
        if total_limit > 0
        else None
    )
    score_history = service.credit_score_history(db, user, granularity, resolved_from, resolved_to)
    return {
        "data": CreditHealthResponse(
            accounts=utilizations,
            overall_utilization=overall,
            credit_score_history=[
                CreditScoreHistoryPoint(date=point_date, value=value)
                for point_date, value in score_history
            ],
        )
    }


@router.get("/investments")
def investments(
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    holdings = service.investment_holdings(db, user)
    return single_page(
        [
            HoldingPerformance(
                id=holding.id,
                account_id=holding.account_id,
                symbol=holding.symbol,
                name=holding.name,
                quantity=holding.quantity,
                cost_basis=holding.cost_basis,
                current_value=holding.current_value,
                gain_loss=(
                    holding.current_value - holding.cost_basis
                    if holding.current_value is not None
                    else None
                ),
                source=holding.source,
            )
            for holding in holdings
        ]
    )
