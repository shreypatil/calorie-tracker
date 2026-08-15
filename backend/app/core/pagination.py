"""One pagination envelope, used by every list endpoint (NFR-3).

`page_size` is capped server-side, so no endpoint can be made to return an
unbounded result set.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings


class Page[T](BaseModel):
    items: list[T]
    page: int
    page_size: int
    total: int
    has_next: bool


@dataclass(frozen=True)
class PageParams:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def page_params(
    page: Annotated[int, Query(ge=1, description="1-indexed page number")] = 1,
    page_size: Annotated[
        int | None, Query(ge=1, description="Items per page; server default when omitted")
    ] = None,
) -> PageParams:
    settings = get_settings()
    effective = page_size or settings.default_page_size
    return PageParams(page=page, page_size=min(effective, settings.max_page_size))


PageParamsDep = Annotated[PageParams, Depends(page_params)]


def paginate(session: Session, stmt: Select, params: PageParams) -> tuple[Sequence, int]:
    """Run `stmt` for one page and return its rows plus the unpaginated total."""
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.execute(stmt.offset(params.offset).limit(params.page_size)).scalars().all()
    return rows, total


def build_page(items: list, total: int, params: PageParams) -> dict:
    return {
        "items": items,
        "page": params.page,
        "page_size": params.page_size,
        "total": total,
        "has_next": params.offset + len(items) < total,
    }
