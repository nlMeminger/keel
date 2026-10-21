import calendar
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session as DbSession

from app.accounts.models import Account
from app.assets.models import Asset
from app.auth.models import User
from app.categories.models import Category
from app.holdings.models import Holding
from app.metrics.models import Metric
from app.transactions.models import Transaction

Granularity = Literal["day", "week", "month"]

#: account_types that reduce net worth rather than add to it (SPEC.md §5 — Account.balance
#: is always non-negative regardless of asset-vs-liability type).
LIABILITY_ACCOUNT_TYPES = {"credit_card", "loan", "mortgage", "student_loan"}


def _period_end_dates(granularity: Granularity, date_from: date, date_to: date) -> list[date]:
    """One date per period between date_from and date_to inclusive — each the last day
    covered by that period (day: itself; week: the following Sunday; month: the month's
    last day), clamped so the final period never runs past date_to."""
    if date_from > date_to:
        return []
    ends: list[date] = []
    if granularity == "day":
        current = date_from
        while current <= date_to:
            ends.append(current)
            current += timedelta(days=1)
    elif granularity == "week":
        current = date_from
        while current <= date_to:
            days_until_sunday = (6 - current.weekday()) % 7
            week_end = min(current + timedelta(days=days_until_sunday), date_to)
            ends.append(week_end)
            current = week_end + timedelta(days=1)
    else:
        current = date_from
        while current <= date_to:
            last_day = calendar.monthrange(current.year, current.month)[1]
            month_end = min(current.replace(day=last_day), date_to)
            ends.append(month_end)
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1, day=1)
            else:
                current = current.replace(month=current.month + 1, day=1)
    return ends


def _period_ranges(
    granularity: Granularity, date_from: date, date_to: date
) -> list[tuple[date, date]]:
    """Start/end pairs covering the same periods as `_period_end_dates`, for reports that sum
    activity *within* a period rather than reading the latest value as of its end."""
    ranges: list[tuple[date, date]] = []
    start = date_from
    for end in _period_end_dates(granularity, date_from, date_to):
        ranges.append((start, end))
        start = end + timedelta(days=1)
    return ranges


def default_history_date_from(db: DbSession, user: User, metric_types: tuple[str, ...]) -> date:
    """Earliest relevant Metric date for this user, or today if none exist yet — used so
    history reports have something sensible to default to with zero Plaid connections."""
    earliest = db.scalar(
        select(func.min(Metric.date)).where(
            Metric.user_id == user.id, Metric.type.in_(metric_types)
        )
    )
    return earliest or date.today()


def current_net_worth(db: DbSession, user: User) -> Decimal:
    """Live sum over active accounts and assets right now — liability account_types
    subtract rather than add. Historical points come from `net_worth_history` instead,
    reconstructed from Metrics, since a deactivated account's past balance still counts."""
    net_worth = Decimal("0")
    for account_type, balance in db.execute(
        select(Account.account_type, Account.balance).where(
            Account.user_id == user.id, Account.is_active.is_(True)
        )
    ).all():
        net_worth += -balance if account_type in LIABILITY_ACCOUNT_TYPES else balance
    assets_total = db.scalar(
        select(func.coalesce(func.sum(Asset.current_value), 0)).where(Asset.user_id == user.id)
    )
    return net_worth + Decimal(assets_total or 0)


def net_worth_history(
    db: DbSession, user: User, granularity: Granularity, date_from: date, date_to: date
) -> list[tuple[date, Decimal]]:
    """Net worth per period, reconstructed purely from account_balance/asset_value Metrics
    (API_SPEC.md §15) — never from the accounts/assets tables' live current values, so a
    since-deactivated account's history is still counted. A period before any Metric exists
    for a given account/asset simply doesn't count it yet (no retroactive backfill)."""
    period_ends = _period_end_dates(granularity, date_from, date_to)
    if not period_ends:
        return []

    account_types = dict(
        db.execute(select(Account.id, Account.account_type).where(Account.user_id == user.id)).all()
    )
    metrics = db.scalars(
        select(Metric)
        .where(
            Metric.user_id == user.id,
            Metric.type.in_(("account_balance", "asset_value")),
            Metric.date <= date_to,
        )
        .order_by(Metric.date)
    ).all()

    latest_account_value: dict[uuid.UUID, Decimal] = {}
    latest_asset_value: dict[uuid.UUID, Decimal] = {}
    results: list[tuple[date, Decimal]] = []
    metric_idx = 0
    for period_end in period_ends:
        while metric_idx < len(metrics) and metrics[metric_idx].date <= period_end:
            metric = metrics[metric_idx]
            if metric.type == "account_balance" and metric.account_id is not None:
                latest_account_value[metric.account_id] = metric.value
            elif metric.type == "asset_value" and metric.asset_id is not None:
                latest_asset_value[metric.asset_id] = metric.value
            metric_idx += 1
        net_worth = Decimal("0")
        for account_id, value in latest_account_value.items():
            account_type = account_types.get(account_id)
            net_worth += -value if account_type in LIABILITY_ACCOUNT_TYPES else value
        net_worth += sum(latest_asset_value.values(), Decimal("0"))
        results.append((period_end, net_worth))
    return results


def cash_flow(
    db: DbSession, user: User, granularity: Granularity, date_from: date, date_to: date
) -> list[tuple[date, date, Decimal, Decimal]]:
    """Inflow/outflow summed within each period (not a latest-value read) — excludes any
    transaction with is_transfer=true (API_SPEC.md §15)."""
    results: list[tuple[date, date, Decimal, Decimal]] = []
    inflow_expr = func.coalesce(
        func.sum(case((Transaction.amount > 0, Transaction.amount), else_=0)), 0
    )
    outflow_expr = func.coalesce(
        func.sum(case((Transaction.amount < 0, -Transaction.amount), else_=0)), 0
    )
    for start, end in _period_ranges(granularity, date_from, date_to):
        inflow, outflow = db.execute(
            select(inflow_expr, outflow_expr).where(
                Transaction.user_id == user.id,
                Transaction.is_transfer.is_(False),
                Transaction.date >= start,
                Transaction.date <= end,
            )
        ).one()
        results.append((start, end, Decimal(inflow), Decimal(outflow)))
    return results


def spending_by_category(
    db: DbSession, user: User, date_from: date, date_to: date
) -> list[tuple[uuid.UUID | None, str | None, Decimal]]:
    """Category breakdown of outflow over a date range — excludes is_transfer=true
    (API_SPEC.md §15). category_id/name are None for uncategorized spend."""
    stmt = (
        select(Category.id, Category.primary_category, func.sum(-Transaction.amount).label("total"))
        .select_from(Transaction)
        .outerjoin(Category, Transaction.category_id == Category.id)
        .where(
            Transaction.user_id == user.id,
            Transaction.is_transfer.is_(False),
            Transaction.amount < 0,
            Transaction.date >= date_from,
            Transaction.date <= date_to,
        )
        .group_by(Category.id, Category.primary_category)
        .order_by(func.sum(-Transaction.amount).desc())
    )
    return [(row.id, row.primary_category, row.total) for row in db.execute(stmt)]


def credit_card_utilization(db: DbSession, user: User) -> list[Account]:
    """Every active credit_card account for charting utilization (balance / detail.credit_limit)
    — computed in the schema layer since `detail` is free-form JSONB here, not a column."""
    return list(
        db.scalars(
            select(Account).where(
                Account.user_id == user.id,
                Account.account_type == "credit_card",
                Account.is_active.is_(True),
            )
        )
    )


def credit_score_history(
    db: DbSession, user: User, granularity: Granularity, date_from: date, date_to: date
) -> list[tuple[date, Decimal]]:
    """Same last-value-per-period rollup as net_worth_history, over the standalone
    `credit_score` Metrics (no account_id/asset_id — API_SPEC.md §14)."""
    period_ends = _period_end_dates(granularity, date_from, date_to)
    if not period_ends:
        return []
    metrics = db.scalars(
        select(Metric)
        .where(Metric.user_id == user.id, Metric.type == "credit_score", Metric.date <= date_to)
        .order_by(Metric.date)
    ).all()

    results: list[tuple[date, Decimal]] = []
    latest_value: Decimal | None = None
    metric_idx = 0
    for period_end in period_ends:
        while metric_idx < len(metrics) and metrics[metric_idx].date <= period_end:
            latest_value = metrics[metric_idx].value
            metric_idx += 1
        if latest_value is not None:
            results.append((period_end, latest_value))
    return results


def investment_holdings(db: DbSession, user: User) -> list[Holding]:
    """Every holding across the user's investment accounts, Plaid-sourced and manual alike
    (API_SPEC.md §15) — ownership is checked via the parent Account, same as 4.14's CRUD."""
    return list(
        db.scalars(
            select(Holding)
            .join(Account, Holding.account_id == Account.id)
            .where(Account.user_id == user.id)
            .order_by(Holding.created_at)
        )
    )
