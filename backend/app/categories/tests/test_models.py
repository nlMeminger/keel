from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.categories.models import TRANSFER_CATEGORY_NAME, Category
from app.categories.seed import SYSTEM_CATEGORIES, seed_categories


def test_seed_creates_every_system_category_with_null_owner(db: OrmSession) -> None:
    # conftest's autouse _reset_schema already seeds once; re-run explicitly to assert shape.
    rows = db.scalars(select(Category).where(Category.owner_id.is_(None))).all()
    names = {row.primary_category for row in rows}
    assert names == set(SYSTEM_CATEGORIES)
    assert all(row.owner_id is None for row in rows)


def test_transfer_category_is_seeded(db: OrmSession) -> None:
    transfer = db.scalar(
        select(Category).where(
            Category.owner_id.is_(None), Category.primary_category == TRANSFER_CATEGORY_NAME
        )
    )
    assert transfer is not None


def test_seeding_twice_does_not_duplicate_rows(db: OrmSession) -> None:
    before = db.scalar(select(Category).where(Category.owner_id.is_(None)).limit(1))
    assert before is not None
    count_before = len(db.scalars(select(Category)).all())

    seed_categories(db)
    seed_categories(db)

    count_after = len(db.scalars(select(Category)).all())
    assert count_after == count_before


def test_custom_category_has_non_null_owner(db: OrmSession) -> None:
    from app.auth.models import User

    user = User(email="categorizer@example.com", password_hash="hashed", name="Categorizer")
    db.add(user)
    db.commit()
    db.refresh(user)

    custom = Category(owner_id=user.id, primary_category="My Hobby")
    db.add(custom)
    db.commit()
    db.refresh(custom)

    assert custom.owner_id == user.id
