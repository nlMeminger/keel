from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.auth.models import User
from app.budgets import service as budgets_service
from app.budgets.models import Budget
from app.metrics.models import Metric
from app.reports import service as reports_service
from app.transactions.models import Transaction

RECENT_TRANSACTIONS_LIMIT = 10


def _this_month_start() -> date:
    return date.today().replace(day=1)


def recent_transactions(db: DbSession, user: User) -> list[Transaction]:
    stmt = (
        select(Transaction)
        .where(Transaction.user_id == user.id)
        .order_by(Transaction.date.desc(), Transaction.created_at.desc())
        .limit(RECENT_TRANSACTIONS_LIMIT)
    )
    return list(db.scalars(stmt).all())


def budget_status(db: DbSession, user: User) -> list[tuple[Budget, Decimal]]:
    budgets = db.scalars(budgets_service.list_budgets_stmt(user)).all()
    return [(budget, budgets_service.compute_budget_spend(db, user, budget)) for budget in budgets]


def latest_credit_score(
    db: DbSession, user: User
) -> tuple[Metric, Literal["up", "down", "flat"] | None] | None:
    rows = db.scalars(
        select(Metric)
        .where(Metric.user_id == user.id, Metric.type == "credit_score")
        .order_by(Metric.date.desc(), Metric.created_at.desc())
        .limit(2)
    ).all()
    if not rows:
        return None
    if len(rows) == 1:
        return rows[0], None
    latest, previous = rows[0], rows[1]
    if latest.value > previous.value:
        trend: Literal["up", "down", "flat"] = "up"
    elif latest.value < previous.value:
        trend = "down"
    else:
        trend = "flat"
    return latest, trend


def net_worth_delta(db: DbSession, user: User, current_net_worth: Decimal) -> Decimal:
    """Delta vs. net worth as of the end of last month, reconstructed from Metrics — if no
    Metric exists yet before this month (e.g. a brand-new account that was never patched),
    the prior period simply counts as 0, same no-retroactive-backfill rule net_worth_history
    already follows."""
    last_month_end = _this_month_start() - timedelta(days=1)
    history = reports_service.net_worth_history(db, user, "day", last_month_end, last_month_end)
    previous = history[0][1] if history else Decimal("0")
    return current_net_worth - previous


def this_month_cash_flow(db: DbSession, user: User) -> tuple[Decimal, Decimal]:
    rows = reports_service.cash_flow(db, user, "month", _this_month_start(), date.today())
    if not rows:
        return Decimal("0"), Decimal("0")
    _start, _end, inflow, outflow = rows[0]
    return inflow, outflow
