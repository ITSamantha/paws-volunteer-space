from fastapi import Depends, Response, status

from app.api.dependencies import CurrentUser, DatabaseSession, Dependencies
from app.api.routers.base.router import BaseRouter, Route
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, UnauthorizedError
from app.schemas.shelters import (
    ContactCreate,
    ContactRead,
    ShelterCreate,
    ShelterRead,
    ShelterUpdate,
)
from app.services.shelters import ShelterService


class SheltersRouter(BaseRouter):
    """Приюты и их контакты."""

    prefix = "/api/shelters"
    tags = ("shelters",)
    dependencies = (Depends(Dependencies.service),)
    errors = (UnauthorizedError, ForbiddenError)

    @staticmethod
    @Route.get(summary="Список приютов", response=list[ShelterRead])
    async def list_all(current_user: CurrentUser, session: DatabaseSession) -> list[ShelterRead]:
        """Все приюты по алфавиту с контактами; доступно любому зарегистрированному пользователю."""
        shelters = await ShelterService(session).list_all()
        items = [ShelterRead.model_validate(shelter) for shelter in shelters]

        return items

    @staticmethod
    @Route.post(
        summary="Добавление приюта",
        response=ShelterRead,
        status_code=status.HTTP_201_CREATED,
        errors=(ConflictError,),
    )
    async def create(
        data: ShelterCreate, current_user: CurrentUser, session: DatabaseSession
    ) -> ShelterRead:
        """Добавляет приют вместе с контактами; организаторам и администраторам."""
        shelter = await ShelterService(session).create(data, current_user)

        return ShelterRead.model_validate(shelter)

    @staticmethod
    @Route.get(
        "/{shelter_id}", summary="Приют по ID", response=ShelterRead, errors=(NotFoundError,)
    )
    async def get(
        shelter_id: int, current_user: CurrentUser, session: DatabaseSession
    ) -> ShelterRead:
        """Возвращает приют с контактами; доступно любому зарегистрированному пользователю."""
        shelter = await ShelterService(session).get(shelter_id)

        return ShelterRead.model_validate(shelter)

    @staticmethod
    @Route.patch(
        "/{shelter_id}",
        summary="Изменение приюта",
        response=ShelterRead,
        errors=(NotFoundError,),
    )
    async def update(
        shelter_id: int, data: ShelterUpdate, current_user: CurrentUser, session: DatabaseSession
    ) -> ShelterRead:
        """Изменяет поля приюта, кроме контактов; организаторам и администраторам."""
        shelter = await ShelterService(session).update(shelter_id, data, current_user)

        return ShelterRead.model_validate(shelter)

    @staticmethod
    @Route.delete(
        "/{shelter_id}",
        summary="Удаление приюта",
        status_code=status.HTTP_204_NO_CONTENT,
        errors=(NotFoundError,),
    )
    async def delete(
        shelter_id: int, current_user: CurrentUser, session: DatabaseSession
    ) -> Response:
        """Мягко удаляет приют; только администраторам."""
        await ShelterService(session).delete(shelter_id, current_user)

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @staticmethod
    @Route.post(
        "/{shelter_id}/contacts",
        summary="Добавление контакта приюта",
        response=ContactRead,
        status_code=status.HTTP_201_CREATED,
        errors=(NotFoundError, ConflictError),
    )
    async def add_contact(
        shelter_id: int, data: ContactCreate, current_user: CurrentUser, session: DatabaseSession
    ) -> ContactRead:
        """Добавляет контакт приюту; организаторам и администраторам."""
        contact = await ShelterService(session).add_contact(shelter_id, data, current_user)

        return ContactRead.model_validate(contact)

    @staticmethod
    @Route.delete(
        "/{shelter_id}/contacts/{contact_id}",
        summary="Удаление контакта приюта",
        status_code=status.HTTP_204_NO_CONTENT,
        errors=(NotFoundError,),
    )
    async def delete_contact(
        shelter_id: int, contact_id: int, current_user: CurrentUser, session: DatabaseSession
    ) -> Response:
        """Удаляет контакт приюта; организаторам и администраторам."""
        await ShelterService(session).delete_contact(shelter_id, contact_id, current_user)

        return Response(status_code=status.HTTP_204_NO_CONTENT)
