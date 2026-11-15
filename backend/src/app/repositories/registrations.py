from collections.abc import Collection

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Registration, User
from app.database.models.enums import RegistrationStatus
from app.schemas.pagination import Pagination


class RegistrationRepository:
    """Доступ к записям волонтёров на мероприятия."""

    def __init__(self, session: AsyncSession) -> None:
        """Работает в переданной сессии."""
        self.__session = session

    async def get(self, event_id: int, user_id: int) -> Registration | None:
        """Запись пользователя на мероприятие."""
        statement = self.__select().where(
            Registration.event_id == event_id, Registration.user_id == user_id
        )
        registration = await self.__session.scalar(statement)

        return registration

    async def get_by_id(self, event_id: int, registration_id: int) -> Registration | None:
        """Запись по ID, если она относится к этому мероприятию."""
        statement = self.__select().where(
            Registration.event_id == event_id, Registration.id == registration_id
        )
        registration = await self.__session.scalar(statement)

        return registration

    async def add(self, registration: Registration) -> None:
        """Добавляет запись."""
        self.__session.add(registration)

        await self.flush()

    async def flush(self) -> None:
        """Записывает изменения."""
        await self.__session.flush()

    async def search_by_event(
        self,
        event_id: int,
        statuses: Collection[RegistrationStatus] | None,
        pagination: Pagination,
    ) -> tuple[list[Registration], int]:
        """Записи на мероприятие в порядке записи; возвращает страницу и общее число."""
        conditions = [Registration.event_id == event_id]

        if statuses:
            conditions.append(Registration.status.in_(statuses))

        total = await self.__session.scalar(
            select(func.count()).select_from(Registration).where(*conditions)
        )
        statement = (
            self.__select()
            .where(*conditions)
            .order_by(Registration.created_at, Registration.id)
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        registrations = await self.__session.scalars(statement)

        return list(registrations), total or 0

    async def search_by_user(
        self,
        user_id: int,
        statuses: Collection[RegistrationStatus] | None,
        pagination: Pagination,
    ) -> tuple[list[Registration], int]:
        """Записи пользователя, новые первыми; возвращает страницу и общее число."""
        conditions = [Registration.user_id == user_id]

        if statuses:
            conditions.append(Registration.status.in_(statuses))

        total = await self.__session.scalar(
            select(func.count()).select_from(Registration).where(*conditions)
        )
        statement = (
            self.__select()
            .where(*conditions)
            .order_by(Registration.created_at.desc(), Registration.id.desc())
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        registrations = await self.__session.scalars(statement)

        return list(registrations), total or 0

    def __select(self) -> Select[Registration]:
        """Базовый запрос: записи с загруженным волонтёром."""
        return (
            select(Registration)
            .options(selectinload(Registration.user).selectinload(User.roles))
            .execution_options(populate_existing=True)
        )
