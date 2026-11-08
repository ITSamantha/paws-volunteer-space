from fastapi import Depends, Response, status

from app.api.dependencies import CurrentUser, DatabaseSession, Dependencies
from app.api.routers.base.router import BaseRouter, Route
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, UnauthorizedError
from app.schemas.base.titles import TitleRead
from app.schemas.event.tag import TagCreate
from app.services.event.tags import TagService


class TagsRouter(BaseRouter):
    """Справочник тегов мероприятий."""

    prefix = "/api/tags"
    tags = ("tags",)
    dependencies = (Depends(Dependencies.service),)
    errors = (UnauthorizedError, ForbiddenError)

    @staticmethod
    @Route.get(summary="Список тегов", response=list[TitleRead])
    async def list_all(current_user: CurrentUser, session: DatabaseSession) -> list[TitleRead]:
        """Все теги по алфавиту; доступно любому зарегистрированному пользователю."""
        tags = await TagService(session).list_all()
        items = [TitleRead.model_validate(tag) for tag in tags]

        return items

    @staticmethod
    @Route.post(
        summary="Добавление тега",
        response=TitleRead,
        status_code=status.HTTP_201_CREATED,
        errors=(ConflictError,),
    )
    async def create(
        data: TagCreate, current_user: CurrentUser, session: DatabaseSession
    ) -> TitleRead:
        """Добавляет тег, если нужного нет в списке; организаторам и администраторам."""
        tag = await TagService(session).create(data.title, current_user)

        return TitleRead.model_validate(tag)

    @staticmethod
    @Route.delete(
        "/{tag_id}",
        summary="Удаление тега",
        status_code=status.HTTP_204_NO_CONTENT,
        errors=(NotFoundError,),
    )
    async def delete(tag_id: int, current_user: CurrentUser, session: DatabaseSession) -> Response:
        """Мягко удаляет тег; у прошедших мероприятий он сохраняется."""
        await TagService(session).delete(tag_id, current_user)

        return Response(status_code=status.HTTP_204_NO_CONTENT)
