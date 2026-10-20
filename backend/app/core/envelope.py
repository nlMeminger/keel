from typing import Generic, TypeVar

from pydantic import BaseModel

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
