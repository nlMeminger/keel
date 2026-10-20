from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.sql import Select

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    data: T


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total_count: int
    total_pages: int


class Page(BaseModel, Generic[T]):
    data: list[T]
    pagination: PaginationMeta


def single_page(items: list[T]) -> dict[str, object]:
    """Wrap an unbounded-but-small collection as a one-page Page response."""
    count = len(items)
    return {
        "data": items,
        "pagination": {"page": 1, "page_size": count, "total_count": count, "total_pages": 1},
    }


def paginate(
    db: DbSession, stmt: Select[Any], page: int, page_size: int
) -> tuple[Sequence[Any], PaginationMeta]:
    """Runs a real LIMIT/OFFSET query plus a COUNT, for lists too large for `single_page`."""
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total_count = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.limit(page_size).offset((page - 1) * page_size)).all()
    total_pages = max(1, -(-total_count // page_size))
    meta = PaginationMeta(
        page=page, page_size=page_size, total_count=total_count, total_pages=total_pages
    )
    return rows, meta
