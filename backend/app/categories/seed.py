from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.categories.models import TRANSFER_CATEGORY_NAME, Category

SYSTEM_CATEGORIES = (
    "Income",
    "Housing",
    "Transportation",
    "Food & Dining",
    "Shopping",
    "Entertainment",
    "Health & Fitness",
    "Travel",
    "Bills & Utilities",
    "Other",
    TRANSFER_CATEGORY_NAME,
)


def seed_categories(db: DbSession) -> None:
    """Idempotently ensures every baseline system category (owner_id IS NULL) exists.

    Called from both the Alembic migration (real deployments) and conftest's _reset_schema
    fixture (tests rebuild the schema via create_all(), never `alembic upgrade head`).
    """
    existing = set(db.scalars(select(Category.primary_category).where(Category.owner_id.is_(None))))
    for name in SYSTEM_CATEGORIES:
        if name not in existing:
            db.add(Category(owner_id=None, primary_category=name))
    db.commit()
