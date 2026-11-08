from fastapi import Depends, Response, status

from app.api.dependencies import CurrentUser, DatabaseSession, Dependencies
from app.api.routers.base.router import BaseRouter, Route
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, UnauthorizedError
from app.schemas.base.titles import TitleRead
from app.schemas.event.bonus import BonusCreate
from app.services.event.bonuses import BonusService


class BonusesRouter(BaseRouter):
    """Справочник бонусов за участие в мероприятиях."""

    prefix = "/api/bonuses"
    tags = ("bonuses",)
    dependencies = (Depends(Dependencies.service),)
    errors = (UnauthorizedError, ForbiddenError)

    @staticmethod
    @Route.get(summary="Список бонусов", response=list[TitleRead])
    async def list_all(current_user: CurrentUser, session: DatabaseSession) -> list[TitleRead]:
        """Все бонусы по алфавиту; доступно любому зарегистрированному пользователю."""
        bonuses = await BonusService(session).list_all()
        items = [TitleRead.model_validate(bonus) for bonus in bonuses]

        return items

    @staticmethod
    @Route.post(
        summary="Добавление бонуса",
        response=TitleRead,
        status_code=status.HTTP_201_CREATED,
        errors=(ConflictError,),
    )
    async def create(
        data: BonusCreate, current_user: CurrentUser, session: DatabaseSession
    ) -> TitleRead:
        """Добавляет бонус, если нужного нет в списке; организаторам и администраторам."""
        bonus = await BonusService(session).create(data.title, current_user)

        return TitleRead.model_validate(bonus)

    @staticmethod
    @Route.delete(
        "/{bonus_id}",
        summary="Удаление бонуса",
        status_code=status.HTTP_204_NO_CONTENT,
        errors=(NotFoundError,),
    )
    async def delete(
        bonus_id: int, current_user: CurrentUser, session: DatabaseSession
    ) -> Response:
        """Мягко удаляет бонус; у прошедших мероприятий он сохраняется."""
        await BonusService(session).delete(bonus_id, current_user)

        return Response(status_code=status.HTTP_204_NO_CONTENT)
