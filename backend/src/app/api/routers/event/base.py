from typing import Annotated

from fastapi import Depends, Query, status
from pydantic import AwareDatetime

from app.api.dependencies import CurrentUser, DatabaseSession, Dependencies, PageParams
from app.api.routers.base.router import BaseRouter, Route
from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    UnprocessableError,
)
from app.database.models.enums import EventStatus
from app.schemas.event.base import (
    EventCancel,
    EventCreate,
    EventFilters,
    EventRead,
    EventSummary,
    EventUpdate,
)
from app.schemas.pagination import Page
from app.services.event.base import EventDetails, EventService


class EventsRouter(BaseRouter):
    """Мероприятия: список, карточка, создание, изменение, отмена и завершение."""

    prefix = "/api/events"
    tags = ("events",)
    dependencies = (Depends(Dependencies.service),)
    errors = (UnauthorizedError, ForbiddenError)

    @staticmethod
    def present(details: EventDetails) -> EventRead:
        """Карточка; ссылка на чат участников остаётся только у тех, кому её можно видеть."""
        data = EventRead.model_validate(details.event)
        link = data.telegram_chat_link if details.can_see_chat else None

        return data.model_copy(update={"occupied": details.occupied, "telegram_chat_link": link})

    @staticmethod
    def summarize(details: EventDetails) -> EventSummary:
        """Мероприятие для списка: без чата, с числом занятых мест."""
        data = EventSummary.model_validate(details.event)

        return data.model_copy(update={"occupied": details.occupied})

    @classmethod
    @Route.get(
        summary="Список мероприятий",
        response=Page[EventSummary],
    )
    async def search(
        cls,
        current_user: CurrentUser,
        session: DatabaseSession,
        pagination: PageParams,
        status_: Annotated[
            EventStatus | None, Query(alias="status", description="Статус мероприятия")
        ] = None,
        shelter_id: Annotated[int | None, Query(description="Приют")] = None,
        starts_from: Annotated[
            AwareDatetime | None, Query(description="Начало не раньше (ISO 8601, с часовым поясом)")
        ] = None,
        starts_to: Annotated[
            AwareDatetime | None, Query(description="Начало не позже (ISO 8601, с часовым поясом)")
        ] = None,
        tag_id: Annotated[int | None, Query(description="Есть этот тег")] = None,
        bonus_id: Annotated[int | None, Query(description="Есть этот бонус")] = None,
    ) -> Page[EventSummary]:
        """Мероприятия по возрастанию даты начала; доступно любому зарегистрированному."""
        filters = EventFilters(status_, shelter_id, starts_from, starts_to, tag_id, bonus_id)
        items, total = await EventService(session).search(filters, pagination, current_user)

        return Page(
            items=[cls.summarize(item) for item in items],
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    @classmethod
    @Route.post(
        summary="Создание мероприятия",
        response=EventRead,
        status_code=status.HTTP_201_CREATED,
        errors=(UnprocessableError,),
    )
    async def create(
        cls, data: EventCreate, current_user: CurrentUser, session: DatabaseSession
    ) -> EventRead:
        """Создаёт мероприятие; организаторам и администраторам.

        Если не указать «одобрять записи» и «что взять», подставятся значения приюта.
        """
        details = await EventService(session).create(data, current_user)

        return cls.present(details)

    @classmethod
    @Route.get(
        "/{event_id}",
        summary="Карточка мероприятия",
        response=EventRead,
        errors=(NotFoundError,),
    )
    async def get(
        cls, event_id: int, current_user: CurrentUser, session: DatabaseSession
    ) -> EventRead:
        """Мероприятие целиком; чат участников видят организаторы и подтверждённые участники."""
        details = await EventService(session).get(event_id, current_user)

        return cls.present(details)

    @classmethod
    @Route.patch(
        "/{event_id}",
        summary="Изменение мероприятия",
        response=EventRead,
        errors=(NotFoundError, ConflictError, UnprocessableError),
    )
    async def update(
        cls,
        event_id: int,
        data: EventUpdate,
        current_user: CurrentUser,
        session: DatabaseSession,
    ) -> EventRead:
        """Изменяет запланированное мероприятие; его организатору и администратору.

        Если изменились время, место или «что взять», участникам уходит уведомление.
        """
        details = await EventService(session).update(event_id, data, current_user)

        return cls.present(details)

    @classmethod
    @Route.post(
        "/{event_id}/cancel",
        summary="Отмена мероприятия",
        response=EventRead,
        errors=(NotFoundError, ConflictError),
    )
    async def cancel(
        cls,
        event_id: int,
        data: EventCancel,
        current_user: CurrentUser,
        session: DatabaseSession,
    ) -> EventRead:
        """Отменяет мероприятие с причиной; участникам уходит уведомление."""
        details = await EventService(session).cancel(event_id, data, current_user)

        return cls.present(details)

    @classmethod
    @Route.post(
        "/{event_id}/complete",
        summary="Завершение мероприятия",
        response=EventRead,
        errors=(NotFoundError, ConflictError),
    )
    async def complete(
        cls, event_id: int, current_user: CurrentUser, session: DatabaseSession
    ) -> EventRead:
        """Завершает мероприятие; доступно только после его начала."""
        details = await EventService(session).complete(event_id, current_user)

        return cls.present(details)
