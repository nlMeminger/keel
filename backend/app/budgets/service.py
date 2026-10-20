import calendar
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session as DbSession

from app.auth.models import User
from app.budgets.models import Budget
from app.categories.models import Category
from app.core.errors import AppError
from app.transactions.models import Transaction


def _validate_category_visible(db: DbSession, user: User, category_id: uuid.UUID | None) -> None:
    if category_id is None:
        return
    category = db.get(Category, category_id)
    if category is None or (category.owner_id is not None and category.owner_id != user.id):
        raise AppError(404, "not_found", "Category not found.")


def _current_period_bounds(start_date: date) -> tuple[date, date]:
    """Calendar month containing today, clipped so the period never starts before the
    budget's own start_date (a budget created mid-month doesn't retroactively pull in
    prior spend)."""
    today = datetime.now(UTC).date()
    first_of_month = today.replace(day=1)
    period_start = max(first_of_month, start_date)
    last_day = calendar.monthrange(today.year, today.month)[1]
    period_end = today.replace(day=last_day)
    return period_start, period_end


def compute_budget_spend(db: DbSession, user: User, budget: Budget) -> Decimal:
    """Always computed live from Transaction rows, never stored. Never counts a transaction
    with is_transfer=true, regardless of its assigned category (SPEC.md §5)."""
    period_start, period_end = _current_period_bounds(budget.start_date)
    stmt = select(func.coalesce(func.sum(-Transaction.amount), 0)).where(
        Transaction.user_id == user.id,
        Transaction.is_transfer.is_(False),
        Transaction.amount < 0,
        Transaction.date >= period_start,
        Transaction.date <= period_end,
    )
    if budget.category_id is not None:
        stmt = stmt.where(Transaction.category_id == budget.category_id)
    return db.scalar(stmt) or Decimal("0")


def create_budget(
    db: DbSession,
    user: User,
    category_id: uuid.UUID | None,
    amount_limit: Decimal,
    start_date: date,
) -> Budget:
    _validate_category_visible(db, user, category_id)
    budget = Budget(
        user_id=user.id, category_id=category_id, amount_limit=amount_limit, start_date=start_date
    )
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return budget


def get_budget(db: DbSession, user: User, budget_id: uuid.UUID) -> Budget:
    budget = db.scalar(select(Budget).where(Budget.id == budget_id, Budget.user_id == user.id))
    if budget is None:
        raise AppError(404, "not_found", "Budget not found.")
    return budget


def list_budgets_stmt(user: User) -> Select[Budget]:
    return select(Budget).where(Budget.user_id == user.id).order_by(Budget.created_at)


def update_budget(
    db: DbSession, user: User, budget_id: uuid.UUID, fields: dict[str, object]
) -> Budget:
    """`fields` comes from the request body's `model_dump(exclude_unset=True)` — an explicit
    `category_id: null` switches the budget to "overall"; omitting it leaves scope untouched."""
    budget = get_budget(db, user, budget_id)
    if "category_id" in fields:
        category_id = fields["category_id"]
        assert category_id is None or isinstance(category_id, uuid.UUID)
        _validate_category_visible(db, user, category_id)
        budget.category_id = category_id
    if "amount_limit" in fields:
        amount_limit = fields["amount_limit"]
        assert isinstance(amount_limit, Decimal)
        budget.amount_limit = amount_limit
    if "start_date" in fields:
        start_date = fields["start_date"]
        assert isinstance(start_date, date)
        budget.start_date = start_date
    db.commit()
    db.refresh(budget)
    return budget


def delete_budget(db: DbSession, user: User, budget_id: uuid.UUID) -> None:
    budget = get_budget(db, user, budget_id)
    db.delete(budget)
    db.commit()
