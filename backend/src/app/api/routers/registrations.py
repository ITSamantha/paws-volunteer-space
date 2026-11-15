from typing import Annotated

from fastapi import Depends, Query, status

from app.api.dependencies import CurrentUser, DatabaseSession, Dependencies, PageParams
from app.api.routers.base.router import BaseRouter, Route
from app.api.routers.event.base import EventsRouter
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, UnauthorizedError
from app.database.models.enums import RegistrationStatus
from app.schemas.pagination import Page
from app.schemas.registrations import (
    Attendance,
    OwnRegistrationRead,
    ParticipantRead,
    RegistrationCancel,
    RegistrationRead,
    RegistrationReject,
)
from app.services.event.base import EventDetails
from app.services.registrations import RegistrationService

StatusFilter = Annotated[
    list[RegistrationStatus] | None,
    Query(alias="status", description="Только записи с этими статусами; можно несколько"),
]


class RegistrationsRouter(BaseRouter):
    """Запись на мероприятия: волонтёр записывается и отменяет, организатор решает и отмечает."""

    prefix = "/api"
    tags = ("registrations",)
    dependencies = (Depends(Dependencies.service),)
    errors = (UnauthorizedError, ForbiddenError)

    @staticmethod
    @Route.post(
        "/events/{event_id}/registrations",
        summary="Запись на мероприятие",
        response=RegistrationRead,
        status_code=status.HTTP_201_CREATED,
        errors=(NotFoundError, ConflictError),
    )
    async def register(
        event_id: int, current_user: CurrentUser, session: DatabaseSession
    ) -> RegistrationRead:
        """Записывает текущего пользователя.

        Статус ответа: registered — место получено; pending — ждёт одобрения организатора;
        waitlisted — мест нет, пользователь в листе ожидания.
        """
        registration = await RegistrationService(session).register(event_id, current_user)

        return RegistrationRead.model_validate(registration)

    @staticmethod
    @Route.get(
        "/events/{event_id}/registrations",
        summary="Участники мероприятия",
        response=Page[ParticipantRead],
        errors=(NotFoundError,),
    )
    async def participants(
        event_id: int,
        current_user: CurrentUser,
        session: DatabaseSession,
        pagination: PageParams,
        status_: StatusFilter = None,
    ) -> Page[ParticipantRead]:
        """Список записавшихся в порядке записи; организаторам и администраторам."""
        registrations, total = await RegistrationService(session).participants(
            event_id, status_, pagination, current_user
        )

        return Page(
            items=[ParticipantRead.model_validate(item) for item in registrations],
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    @staticmethod
    @Route.get(
        "/events/{event_id}/registrations/me",
        summary="Моя запись на мероприятие",
        response=RegistrationRead,
        errors=(NotFoundError,),
    )
    async def own(
        event_id: int, current_user: CurrentUser, session: DatabaseSession
    ) -> RegistrationRead:
        """Запись текущего пользователя; 404, если он не записан."""
        registration = await RegistrationService(session).own(event_id, current_user)

        return RegistrationRead.model_validate(registration)

    @staticmethod
    @Route.post(
        "/events/{event_id}/registrations/me/claim",
        summary="Занять освободившееся место",
        response=RegistrationRead,
        errors=(NotFoundError, ConflictError),
    )
    async def claim(
        event_id: int, current_user: CurrentUser, session: DatabaseSession
    ) -> RegistrationRead:
        """Переводит из листа ожидания в записанные; если места снова заняли, вернёт 409."""
        registration = await RegistrationService(session).claim(event_id, current_user)

        return RegistrationRead.model_validate(registration)

    @staticmethod
    @Route.post(
        "/events/{event_id}/registrations/me/cancel",
        summary="Отмена своей записи",
        response=RegistrationRead,
        errors=(NotFoundError, ConflictError),
    )
    async def cancel(
        event_id: int,
        data: RegistrationCancel,
        current_user: CurrentUser,
        session: DatabaseSession,
    ) -> RegistrationRead:
        """Отменяет запись с причиной: организатор узнаёт об отмене, лист ожидания — о месте."""
        registration = await RegistrationService(session).cancel(event_id, data, current_user)

        return RegistrationRead.model_validate(registration)

    @staticmethod
    @Route.post(
        "/events/{event_id}/registrations/{registration_id}/approve",
        summary="Одобрение заявки",
        response=ParticipantRead,
        errors=(NotFoundError, ConflictError),
    )
    async def approve(
        event_id: int, registration_id: int, current_user: CurrentUser, session: DatabaseSession
    ) -> ParticipantRead:
        """Одобряет заявку; только организатор, создавший мероприятие."""
        registration = await RegistrationService(session).approve(
            event_id, registration_id, current_user
        )

        return ParticipantRead.model_validate(registration)

    @staticmethod
    @Route.post(
        "/events/{event_id}/registrations/{registration_id}/reject",
        summary="Отклонение заявки",
        response=ParticipantRead,
        errors=(NotFoundError, ConflictError),
    )
    async def reject(
        event_id: int,
        registration_id: int,
        data: RegistrationReject,
        current_user: CurrentUser,
        session: DatabaseSession,
    ) -> ParticipantRead:
        """Отклоняет заявку с причиной; только организатор, создавший мероприятие."""
        registration = await RegistrationService(session).reject(
            event_id, registration_id, data, current_user
        )

        return ParticipantRead.model_validate(registration)

    @staticmethod
    @Route.post(
        "/events/{event_id}/registrations/{registration_id}/attendance",
        summary="Отметка о посещении",
        response=ParticipantRead,
        errors=(NotFoundError, ConflictError),
    )
    async def attendance(
        event_id: int,
        registration_id: int,
        data: Attendance,
        current_user: CurrentUser,
        session: DatabaseSession,
    ) -> ParticipantRead:
        """Отмечает, пришёл ли участник; после начала мероприятия, организатору и администратору."""
        registration = await RegistrationService(session).mark_attendance(
            event_id, registration_id, data.attended, current_user
        )

        return ParticipantRead.model_validate(registration)

    @staticmethod
    @Route.get(
        "/registrations/me",
        summary="Мои записи",
        response=Page[OwnRegistrationRead],
    )
    async def own_list(
        current_user: CurrentUser,
        session: DatabaseSession,
        pagination: PageParams,
        status_: StatusFilter = None,
    ) -> Page[OwnRegistrationRead]:
        """Все записи текущего пользователя с мероприятиями, новые первыми."""
        items, total = await RegistrationService(session).own_list(
            status_, pagination, current_user
        )
        result = []

        for item in items:
            base = RegistrationRead.model_validate(item.registration).model_dump()
            event = EventsRouter.summarize(EventDetails(item.event, item.occupied, False))
            result.append(OwnRegistrationRead(**base, event=event))

        return Page(items=result, total=total, limit=pagination.limit, offset=pagination.offset)
