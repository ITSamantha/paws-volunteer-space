from abc import ABC, abstractmethod
from importlib.resources import files
from importlib.resources.abc import Traversable
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession


class Seeder(ABC):
    """Начальное заполнение таблицы из JSON-файла.

    Повторный запуск безопасен: существующие записи не меняются.
    """

    DATA_DIRECTORY: ClassVar[Traversable] = files("app.database.seeders") / "data"

    @abstractmethod
    async def run(self, session: AsyncSession) -> None:
        """Заполняет таблицу начальными данными."""
