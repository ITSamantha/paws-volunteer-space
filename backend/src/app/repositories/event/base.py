from collections.abc import Collection

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Bonus, Event, Registration, Tag, User
from app.database.models.enums import RegistrationStatus
from app.schemas.event.base import EventFilters
from app.schemas.pagination import Pagination


class EventRepository:
    """Доступ к мероприятиям, их бонусам, тегам и занятым местам."""

    def __init__(self, session: AsyncSession) -> None:
        """Работает в переданной сессии."""
        self.__session = session

    async def get(self, event_id: int) -> Event | None:
        """Находит мероприятие по ID вместе с приютом, бонусами и тегами."""
        event = await self.__session.scalar(self.__select().where(Event.id == event_id))

        return event

    async def get_many(self, event_ids: Collection[int]) -> list[Event]:
        """Находит мероприятия по ID вместе с приютом, бонусами и тегами."""
        events = await self.__session.scalars(self.__select().where(Event.id.in_(event_ids)))

        return list(events)

    async def search(
        self, filters: EventFilters, pagination: Pagination
    ) -> tuple[list[Event], int]:
        """Ищет мероприятия по фильтрам; возвращает страницу и общее число найденных."""
        conditions = []

        if filters.status is not None:
            conditions.append(Event.status == filters.status)

        if filters.shelter_id is not None:
            conditions.append(Event.shelter_id == filters.shelter_id)

        if filters.starts_from is not None:
            conditions.append(Event.starts_at >= filters.starts_from)

        if filters.starts_to is not None:
            conditions.append(Event.starts_at <= filters.starts_to)

        if filters.tag_id is not None:
            conditions.append(Event.tags.any(Tag.id == filters.tag_id))

        if filters.bonus_id is not None:
            conditions.append(Event.bonuses.any(Bonus.id == filters.bonus_id))

        total = await self.__session.scalar(
            select(func.count()).select_from(Event).where(*conditions)
        )
        statement = (
            self.__select()
            .where(*conditions)
            .order_by(Event.starts_at, Event.id)
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        events = await self.__session.scalars(statement)

        return list(events), total or 0

    async def lock(self, event_id: int) -> None:
        """Блокирует строку мероприятия до конца транзакции: записи на него идут по очереди."""
        await self.__session.execute(select(Event.id).where(Event.id == event_id).with_for_update())

    async def add(self, event: Event) -> None:
        """Добавляет мероприятие."""
        self.__session.add(event)

        await self.flush()

    async def flush(self) -> None:
        """Записывает изменения."""
        await self.__session.flush()

    async def occupied(self, event_ids: Collection[int]) -> dict[int, int]:
        """Сколько мест занято в каждом из мероприятий."""
        statement = (
            select(Registration.event_id, func.count())
            .where(
                Registration.event_id.in_(event_ids),
                Registration.status.in_(Registration.OCCUPYING_STATUSES),
            )
            .group_by(Registration.event_id)
        )
        rows = await self.__session.execute(statement)
        counts = dict(rows.all())

        return counts

    async def has_registration(
        self, event_id: int, user_id: int, statuses: Collection[RegistrationStatus]
    ) -> bool:
        """Есть ли у пользователя запись на мероприятие с одним из статусов."""
        statement = select(Registration.id).where(
            Registration.event_id == event_id,
            Registration.user_id == user_id,
            Registration.status.in_(statuses),
        )
        found = await self.__session.scalar(statement)

        return found is not None

    async def participant_ids(
        self, event_id: int, statuses: Collection[RegistrationStatus]
    ) -> list[int]:
        """Пользователи, у которых есть запись на мероприятие с одним из статусов."""
        statement = select(Registration.user_id).where(
            Registration.event_id == event_id, Registration.status.in_(statuses)
        )
        user_ids = await self.__session.scalars(statement)

        return list(user_ids)

    async def find_bonuses(self, bonus_ids: Collection[int]) -> list[Bonus]:
        """Находит не удалённые бонусы по ID."""
        statement = select(Bonus).where(Bonus.id.in_(bonus_ids), Bonus.deleted_at.is_(None))
        bonuses = await self.__session.scalars(statement)

        return list(bonuses)

    async def find_tags(self, tag_ids: Collection[int]) -> list[Tag]:
        """Находит не удалённые теги по ID."""
        statement = select(Tag).where(Tag.id.in_(tag_ids), Tag.deleted_at.is_(None))
        tags = await self.__session.scalars(statement)

        return list(tags)

    def __select(self) -> Select[Event]:
        """Базовый запрос: мероприятия с загруженными приютом, бонусами и тегами."""
        return (
            select(Event)
            .options(
                selectinload(Event.shelter),
                selectinload(Event.creator).selectinload(User.roles),
                selectinload(Event.bonuses),
                selectinload(Event.tags),
            )
            .execution_options(populate_existing=True)
        )
