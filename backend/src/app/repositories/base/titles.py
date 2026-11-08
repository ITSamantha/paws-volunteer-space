from datetime import UTC, datetime
from typing import Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.database.models import Bonus, Tag

Model = TypeVar("Model", Bonus, Tag)


class TitleRepository(Generic[Model]):
    """Доступ к справочнику с одним названием. Мягко удалённые записи не возвращаются."""

    def __init__(
        self,
        session: AsyncSession,
        model: type[Model],
        unique_constraint: str,
        duplicate_message: str,
    ) -> None:
        """Работает со справочником model; при дубле названия выбрасывает ConflictError."""
        self.__session = session
        self.__model: type[Model] = model
        self.__unique_constraint = unique_constraint
        self.__duplicate_message = duplicate_message

    async def list_all(self) -> list[Model]:
        """Все записи по алфавиту."""
        statement = (
            select(self.__model)
            .where(self.__model.deleted_at.is_(None))
            .order_by(func.lower(self.__model.title), self.__model.id)
        )
        items = await self.__session.scalars(statement)

        return list(items)

    async def get(self, item_id: int) -> Model | None:
        """Находит запись по ID."""
        statement = select(self.__model).where(
            self.__model.id == item_id, self.__model.deleted_at.is_(None)
        )
        item = await self.__session.scalar(statement)

        return item

    async def add(self, title: str, created_by: int) -> Model:
        """Добавляет запись; название должно быть уникальным без учёта регистра."""
        item = self.__model(title=title, created_by=created_by)

        try:
            async with self.__session.begin_nested():
                self.__session.add(item)
                await self.__session.flush()
        except IntegrityError as error:
            if self.__unique_constraint in str(error.orig):
                raise ConflictError(self.__duplicate_message) from None

            raise

        return item

    async def delete(self, item: Model) -> None:
        """Мягко удаляет запись: название освобождается для повторного использования."""
        item.deleted_at = datetime.now(UTC)

        await self.__session.flush()
