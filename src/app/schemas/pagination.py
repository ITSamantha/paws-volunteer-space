from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


@dataclass(frozen=True)
class Pagination:
    """Параметры страницы."""

    limit: int
    offset: int


class Page(BaseModel, Generic[T]):
    """Страница результатов и общее число записей."""

    items: list[T]
    total: int
    limit: int
    offset: int
