from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


@dataclass(frozen=True)
class Pagination:
    """Параметры страницы."""

    limit: int
    offset: int


class Page(BaseModel, Generic[T]):
    """Страница результатов и общее число записей."""

    items: list[T] = Field(description="Записи текущей страницы")
    total: int = Field(description="Сколько всего записей подходит под фильтры")
    limit: int = Field(description="Размер страницы")
    offset: int = Field(description="Сколько записей пропущено")
