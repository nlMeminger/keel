import uuid

from sqlalchemy import Select, func, or_, select, update
from sqlalchemy.orm import Session as DbSession

from app.auth.models import User
from app.budgets.models import Budget
from app.categories.models import Category
from app.category_rules.models import CategoryRule
from app.core.errors import AppError
from app.transactions.models import Transaction


def create_category(
    db: DbSession,
    user: User,
    primary_category: str,
    detailed_category: str | None,
    icon: str | None,
    color: str | None,
) -> Category:
    category = Category(
        owner_id=user.id,
        primary_category=primary_category,
        detailed_category=detailed_category,
        icon=icon,
        color=color,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def list_categories_stmt(user: User, scope: str) -> Select[Category]:
    stmt = select(Category)
    if scope == "system":
        stmt = stmt.where(Category.owner_id.is_(None))
    elif scope == "custom":
        stmt = stmt.where(Category.owner_id == user.id)
    else:
        stmt = stmt.where(or_(Category.owner_id.is_(None), Category.owner_id == user.id))
    return stmt.order_by(Category.primary_category)


def _get_category_for_edit(db: DbSession, user: User, category_id: uuid.UUID) -> Category:
    """Looked up once by PATCH and DELETE, both of which share the same visibility rules:
    missing -> 404, system (owner_id NULL) -> 403, someone else's custom -> 404 (masked)."""
    category = db.get(Category, category_id)
    if category is None:
        raise AppError(404, "not_found", "Category not found.")
    if category.owner_id is None:
        raise AppError(403, "system_category_readonly", "System categories cannot be modified.")
    if category.owner_id != user.id:
        raise AppError(404, "not_found", "Category not found.")
    return category


def update_category(
    db: DbSession,
    user: User,
    category_id: uuid.UUID,
    primary_category: str | None,
    detailed_category: str | None,
    icon: str | None,
    color: str | None,
) -> Category:
    category = _get_category_for_edit(db, user, category_id)
    if primary_category is not None:
        category.primary_category = primary_category
    if detailed_category is not None:
        category.detailed_category = detailed_category
    if icon is not None:
        category.icon = icon
    if color is not None:
        category.color = color
    db.commit()
    db.refresh(category)
    return category


def _visible_category_or_none(db: DbSession, user: User, category_id: uuid.UUID) -> Category | None:
    category = db.get(Category, category_id)
    if category is None:
        return None
    if category.owner_id is not None and category.owner_id != user.id:
        return None
    return category


def delete_category(
    db: DbSession, user: User, category_id: uuid.UUID, reassign_to: uuid.UUID | None
) -> None:
    category = _get_category_for_edit(db, user, category_id)

    transaction_count = (
        db.scalar(
            select(func.count())
            .select_from(Transaction)
            .where(Transaction.category_id == category_id)
        )
        or 0
    )
    budget_count = (
        db.scalar(select(func.count()).select_from(Budget).where(Budget.category_id == category_id))
        or 0
    )
    # CategoryRule.category_id is NOT NULL (a rule with no target category makes no sense),
    # so it can't fall out of this check the way Transaction/Budget do via reassignment —
    # it must always be reassigned rather than left referencing a deleted category.
    rule_count = (
        db.scalar(
            select(func.count())
            .select_from(CategoryRule)
            .where(CategoryRule.category_id == category_id)
        )
        or 0
    )
    if transaction_count + budget_count + rule_count > 0:
        if reassign_to is None:
            raise AppError(
                409,
                "category_in_use",
                "Category is still referenced by transactions, budgets, or category rules.",
            )
        target = _visible_category_or_none(db, user, reassign_to)
        if target is None:
            raise AppError(404, "not_found", "reassign_to category not found.")
        db.execute(
            update(Transaction)
            .where(Transaction.category_id == category_id)
            .values(category_id=reassign_to)
        )
        db.execute(
            update(Budget).where(Budget.category_id == category_id).values(category_id=reassign_to)
        )
        db.execute(
            update(CategoryRule)
            .where(CategoryRule.category_id == category_id)
            .values(category_id=reassign_to)
        )

    db.delete(category)
    db.commit()
