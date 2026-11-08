from typing import Generic

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.database.models import User
from app.repositories.base.titles import Model, TitleRepository
from app.services.access import Access


class TitleService(Generic[Model]):
    """Сценарии справочника с одним названием: смотреть может любой, менять — персонал."""

    def __init__(
        self, session: AsyncSession, repository: TitleRepository[Model], label: str
    ) -> None:
        """Работает в переданной сессии; label — как называть запись в сообщениях."""
        self.__session = session
        self.__repository: TitleRepository[Model] = repository
        self.__label = label

    async def list_all(self) -> list[Model]:
        """Все записи справочника."""
        items = await self.__repository.list_all()

        return items

    async def create(self, title: str, current_user: User) -> Model:
        """Добавляет запись; организаторы и администраторы."""
        Access.require_staff(current_user)

        item = await self.__repository.add(title, current_user.id)
        await self.__session.commit()

        return item

    async def delete(self, item_id: int, current_user: User) -> None:
        """Мягко удаляет запись; организаторы и администраторы."""
        Access.require_staff(current_user)

        item = await self.__repository.get(item_id)

        if item is None:
            raise NotFoundError(f"{self.__label} не найден")

        await self.__repository.delete(item)
        await self.__session.commit()
