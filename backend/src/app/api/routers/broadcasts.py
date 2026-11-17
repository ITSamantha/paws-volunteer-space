from fastapi import Depends, status

from app.api.dependencies import CurrentUser, DatabaseSession, Dependencies, PageParams
from app.api.routers.base.router import BaseRouter, Route
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, UnauthorizedError
from app.schemas.broadcasts import BroadcastCreate, BroadcastRead, BroadcastUpdate
from app.schemas.pagination import Page
from app.services.broadcasts import BroadcastService


class BroadcastsRouter(BaseRouter):
    """Черновики рассылок."""

    prefix = "/api/broadcasts"
    tags = ("broadcasts",)
    dependencies = (Depends(Dependencies.service),)
    errors = (UnauthorizedError, ForbiddenError)

    @staticmethod
    @Route.get(summary="Список рассылок", response=Page[BroadcastRead])
    async def search(
        current_user: CurrentUser, session: DatabaseSession, pagination: PageParams
    ) -> Page[BroadcastRead]:
        """Рассылки, сначала новые; администраторам, организаторам и SMM."""
        broadcasts, total = await BroadcastService(session).search(pagination, current_user)

        return Page(
            items=[BroadcastRead.model_validate(item) for item in broadcasts],
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    @staticmethod
    @Route.post(
        summary="Черновик рассылки",
        response=BroadcastRead,
        status_code=status.HTTP_201_CREATED,
    )
    async def create(
        data: BroadcastCreate, current_user: CurrentUser, session: DatabaseSession
    ) -> BroadcastRead:
        """Сохраняет черновик и никому его не отправляет."""
        broadcast = await BroadcastService(session).create(data, current_user)

        return BroadcastRead.model_validate(broadcast)

    @staticmethod
    @Route.get(
        "/{broadcast_id}",
        summary="Рассылка по ID",
        response=BroadcastRead,
        errors=(NotFoundError,),
    )
    async def get(
        broadcast_id: int, current_user: CurrentUser, session: DatabaseSession
    ) -> BroadcastRead:
        """Карточка рассылки."""
        broadcast = await BroadcastService(session).get(broadcast_id, current_user)

        return BroadcastRead.model_validate(broadcast)

    @staticmethod
    @Route.patch(
        "/{broadcast_id}",
        summary="Правка черновика",
        response=BroadcastRead,
        errors=(NotFoundError, ConflictError),
    )
    async def update(
        broadcast_id: int,
        data: BroadcastUpdate,
        current_user: CurrentUser,
        session: DatabaseSession,
    ) -> BroadcastRead:
        """Правит черновик. Чужой черновик может править только администратор."""
        broadcast = await BroadcastService(session).update(broadcast_id, data, current_user)

        return BroadcastRead.model_validate(broadcast)

    @staticmethod
    @Route.post(
        "/{broadcast_id}/send",
        summary="Отправка рассылки",
        response=BroadcastRead,
        errors=(NotFoundError, ConflictError),
    )
    async def send(
        broadcast_id: int, current_user: CurrentUser, session: DatabaseSession
    ) -> BroadcastRead:
        """Отправляет черновик аудитории и помечает его отправленным."""
        broadcast = await BroadcastService(session).send(broadcast_id, current_user)

        return BroadcastRead.model_validate(broadcast)
