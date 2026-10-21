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


def seed_categories(db: DbSession) -> int:
    """Idempotently ensures every baseline system category (owner_id IS NULL) exists.

    Called from the Alembic migration (real deployments), conftest's _reset_schema fixture
    (tests rebuild the schema via create_all(), never `alembic upgrade head`), and
    POST /admin/categories/seed (API_SPEC.md §18, ROADMAP 8.7). Returns the count of newly
    created rows, ignored by the first two callers, read by the third.
    """
    existing = set(db.scalars(select(Category.primary_category).where(Category.owner_id.is_(None))))
    created = 0
    for name in SYSTEM_CATEGORIES:
        if name not in existing:
            db.add(Category(owner_id=None, primary_category=name))
            created += 1
    db.commit()
    return created
