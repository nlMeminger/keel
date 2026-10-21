import uuid
from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session as DbSession

from app.accounts.models import Account
from app.auth.models import User
from app.categories.models import Category
from app.category_rules.models import CategoryRule
from app.core.errors import AppError
from app.transactions.models import Transaction


def _validate_category_owned(db: DbSession, user: User, category_id: uuid.UUID) -> None:
    category = db.get(Category, category_id)
    if category is None or (category.owner_id is not None and category.owner_id != user.id):
        raise AppError(404, "not_found", "Category not found.")


def _validate_account_owned(db: DbSession, user: User, account_id: uuid.UUID | None) -> None:
    if account_id is None:
        return
    account = db.scalar(select(Account).where(Account.id == account_id, Account.user_id == user.id))
    if account is None:
        raise AppError(404, "not_found", "Account not found.")


def create_rule(
    db: DbSession,
    user: User,
    category_id: uuid.UUID,
    merchant_contains: str | None,
    amount_min: Decimal | None,
    amount_max: Decimal | None,
    account_id: uuid.UUID | None,
    priority: int,
    active: bool,
) -> CategoryRule:
    _validate_category_owned(db, user, category_id)
    _validate_account_owned(db, user, account_id)
    rule = CategoryRule(
        user_id=user.id,
        category_id=category_id,
        merchant_contains=merchant_contains,
        amount_min=amount_min,
        amount_max=amount_max,
        account_id=account_id,
        priority=priority,
        active=active,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def get_rule(db: DbSession, user: User, rule_id: uuid.UUID) -> CategoryRule:
    rule = db.scalar(
        select(CategoryRule).where(CategoryRule.id == rule_id, CategoryRule.user_id == user.id)
    )
    if rule is None:
        raise AppError(404, "not_found", "Category rule not found.")
    return rule


def list_rules_stmt(user: User) -> Select[CategoryRule]:
    return (
        select(CategoryRule)
        .where(CategoryRule.user_id == user.id)
        .order_by(CategoryRule.priority, CategoryRule.created_at)
    )


def update_rule(
    db: DbSession, user: User, rule_id: uuid.UUID, fields: dict[str, object]
) -> CategoryRule:
    """`fields` comes from `model_dump(exclude_unset=True)` — only keys the client actually
    sent are present, so an omitted field is left untouched while an explicit null clears it
    (e.g. removing a rule's account scoping)."""
    rule = get_rule(db, user, rule_id)
    if "category_id" in fields:
        category_id = fields["category_id"]
        assert isinstance(category_id, uuid.UUID)
        _validate_category_owned(db, user, category_id)
        rule.category_id = category_id
    if "account_id" in fields:
        account_id = fields["account_id"]
        assert account_id is None or isinstance(account_id, uuid.UUID)
        _validate_account_owned(db, user, account_id)
        rule.account_id = account_id
    if "merchant_contains" in fields:
        merchant_contains = fields["merchant_contains"]
        assert merchant_contains is None or isinstance(merchant_contains, str)
        rule.merchant_contains = merchant_contains
    if "amount_min" in fields:
        amount_min = fields["amount_min"]
        assert amount_min is None or isinstance(amount_min, Decimal)
        rule.amount_min = amount_min
    if "amount_max" in fields:
        amount_max = fields["amount_max"]
        assert amount_max is None or isinstance(amount_max, Decimal)
        rule.amount_max = amount_max
    if "priority" in fields:
        priority = fields["priority"]
        assert isinstance(priority, int)
        rule.priority = priority
    if "active" in fields:
        active = fields["active"]
        assert isinstance(active, bool)
        rule.active = active
    db.commit()
    db.refresh(rule)
    return rule


def delete_rule(db: DbSession, user: User, rule_id: uuid.UUID) -> None:
    rule = get_rule(db, user, rule_id)
    db.delete(rule)
    db.commit()


def _matches(
    txn: Transaction,
    merchant_contains: str | None,
    amount_min: Decimal | None,
    amount_max: Decimal | None,
    account_id: uuid.UUID | None,
) -> bool:
    """All provided conditions are AND-ed (API_SPEC.md §7); a rule with no conditions at all
    matches every uncategorized transaction."""
    if merchant_contains is not None and merchant_contains.lower() not in txn.description.lower():
        return False
    if amount_min is not None and txn.amount < amount_min:
        return False
    if amount_max is not None and txn.amount > amount_max:
        return False
    if account_id is not None and txn.account_id != account_id:
        return False
    return True


def find_matches_for_conditions(
    db: DbSession,
    user: User,
    merchant_contains: str | None,
    amount_min: Decimal | None,
    amount_max: Decimal | None,
    account_id: uuid.UUID | None,
) -> list[Transaction]:
    """Backs `/category-rules/test` — dry-run against the user's existing uncategorized
    transactions without writing anything."""
    _validate_account_owned(db, user, account_id)
    candidates = db.scalars(
        select(Transaction).where(Transaction.user_id == user.id, Transaction.category_id.is_(None))
    ).all()
    return [
        txn
        for txn in candidates
        if _matches(txn, merchant_contains, amount_min, amount_max, account_id)
    ]


def apply_active_rules(db: DbSession, user_id: uuid.UUID) -> dict[str, int]:
    """Backs the `category_rule_apply` job body: applies every active rule, in ascending
    `priority` order, to the user's uncategorized transactions — first match wins per
    transaction (API_SPEC.md §7)."""
    rules = db.scalars(
        select(CategoryRule)
        .where(CategoryRule.user_id == user_id, CategoryRule.active.is_(True))
        .order_by(CategoryRule.priority, CategoryRule.created_at)
    ).all()
    txns = db.scalars(
        select(Transaction).where(Transaction.user_id == user_id, Transaction.category_id.is_(None))
    ).all()

    matched_count = 0
    for txn in txns:
        for rule in rules:
            if _matches(
                txn, rule.merchant_contains, rule.amount_min, rule.amount_max, rule.account_id
            ):
                txn.category_id = rule.category_id
                matched_count += 1
                break
    db.commit()
    return {"matched_count": matched_count}
