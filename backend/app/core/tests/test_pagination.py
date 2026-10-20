from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.core.envelope import paginate
from app.jobs.models import Job


def _seed_jobs(db: DbSession, count: int) -> None:
    for _ in range(count):
        db.add(Job(type="bulk_import", owner_id=None))
    db.commit()


def test_paginate_returns_correct_page_and_counts(db: DbSession) -> None:
    _seed_jobs(db, 7)
    stmt = select(Job).order_by(Job.created_at)

    rows, meta = paginate(db, stmt, page=1, page_size=3)
    assert len(rows) == 3
    assert meta.total_count == 7
    assert meta.total_pages == 3
    assert meta.page == 1
    assert meta.page_size == 3

    rows, meta = paginate(db, stmt, page=3, page_size=3)
    assert len(rows) == 1
    assert meta.total_count == 7
    assert meta.total_pages == 3


def test_paginate_page_beyond_last_returns_empty_not_an_error(db: DbSession) -> None:
    _seed_jobs(db, 2)
    stmt = select(Job).order_by(Job.created_at)

    rows, meta = paginate(db, stmt, page=5, page_size=10)
    assert rows == []
    assert meta.total_count == 2
    assert meta.total_pages == 1


def test_paginate_on_empty_table_returns_one_total_page_not_zero(db: DbSession) -> None:
    stmt = select(Job).order_by(Job.created_at)

    rows, meta = paginate(db, stmt, page=1, page_size=25)
    assert rows == []
    assert meta.total_count == 0
    assert meta.total_pages == 1
