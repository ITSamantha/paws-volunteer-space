from typing import Annotated

from fastapi import Depends, Query, Response, status

from app.api.dependencies import (
    CurrentTelegramId,
    CurrentUser,
    DatabaseSession,
    Dependencies,
    PageParams,
)
from app.api.routing import BaseRouter, Route
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, UnauthorizedError
from app.database.models import User
from app.database.models.enums import RoleType, UserStatus
from app.schemas.pagination import Page
from app.schemas.users import (
    BlockRequest,
    UnblockRequest,
    UserCreate,
    UserFilters,
    UserRead,
    UserUpdate,
)
from app.services.access import Access
from app.services.users import UserService


class UsersRouter(BaseRouter):
    """Пользователи: регистрация, профиль, блокировка, роли."""

    prefix = "/api/users"
    tags = ("users",)
    dependencies = (Depends(Dependencies.service),)
    errors = (UnauthorizedError,)

    @staticmethod
    def present(user: User, viewer: User | None) -> UserRead:
        """Комментарий (например, причина блокировки) видят только организаторы и админы."""
        data = UserRead.model_validate(user)

        if viewer is None or not Access.is_staff(viewer):
            return data.model_copy(update={"comment": None})

        return data

    @classmethod
    @Route.post(
        "",
        status_code=status.HTTP_201_CREATED,
        summary="Регистрация волонтёра",
        response=UserRead,
        errors=(ConflictError,),
    )
    async def register(cls, data: UserCreate, session: DatabaseSession) -> UserRead:
        """Регистрирует волонтёра; нужно согласие на обработку персональных данных."""
        user = await UserService(session).register(data)

        return cls.present(user, viewer=None)

    @classmethod
    @Route.get(
        "/by-telegram/{telegram_id}",
        summary="Пользователь по Telegram ID",
        response=UserRead,
        errors=(
            ForbiddenError,
            NotFoundError,
        ),
    )
    async def get_by_telegram_id(
        cls, telegram_id: int, current_telegram_id: CurrentTelegramId, session: DatabaseSession
    ) -> UserRead:
        """Возвращает пользователя по Telegram ID; чужого — только организатору и админу."""
        user = await UserService(session).get_by_telegram_id(telegram_id, current_telegram_id)

        return cls.present(user, viewer=user if user.telegram_id == current_telegram_id else None)

    @classmethod
    @Route.get(
        "/{user_id}",
        summary="Пользователь по ID",
        response=UserRead,
        errors=(
            ForbiddenError,
            NotFoundError,
        ),
    )
    async def get(
        cls, user_id: int, current_user: CurrentUser, session: DatabaseSession
    ) -> UserRead:
        """Возвращает пользователя по ID: свой профиль или любой — организатору и админу."""
        user = await UserService(session).get(user_id, current_user)

        return cls.present(user, viewer=current_user)

    @classmethod
    @Route.patch(
        "/{user_id}",
        summary="Обновление профиля",
        response=UserRead,
        errors=(
            ForbiddenError,
            NotFoundError,
            ConflictError,
        ),
    )
    async def update(
        cls, user_id: int, data: UserUpdate, current_user: CurrentUser, session: DatabaseSession
    ) -> UserRead:
        """Обновляет профиль и настройки уведомлений: свой — пользователь, любой — админ."""
        user = await UserService(session).update(user_id, data, current_user)

        return cls.present(user, viewer=current_user)

    @classmethod
    @Route.get(summary="Поиск пользователей", response=Page[UserRead], errors=(ForbiddenError,))
    async def search(
        cls,
        current_user: CurrentUser,
        session: DatabaseSession,
        pagination: PageParams,
        status_: Annotated[
            UserStatus | None, Query(alias="status", description="Статус пользователя")
        ] = None,
        role: Annotated[
            RoleType | None, Query(description="Есть ли у пользователя эта роль")
        ] = None,
        full_name: Annotated[
            str | None, Query(max_length=255, description="Часть ФИО, без учёта регистра")
        ] = None,
        phone: Annotated[
            str | None, Query(max_length=16, description="Часть номера телефона")
        ] = None,
    ) -> Page[UserRead]:
        """Ищет пользователей по статусу, роли, ФИО и телефону; только организаторам и админам."""
        filters = UserFilters(status=status_, role=role, full_name=full_name, phone=phone)
        users, total = await UserService(session).search(filters, pagination, current_user)

        return Page(
            items=[cls.present(user, viewer=current_user) for user in users],
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    @classmethod
    @Route.post(
        "/{user_id}/block",
        summary="Блокировка пользователя",
        response=UserRead,
        errors=(
            ForbiddenError,
            NotFoundError,
        ),
    )
    async def block(
        cls, user_id: int, data: BlockRequest, current_user: CurrentUser, session: DatabaseSession
    ) -> UserRead:
        """Блокирует пользователя; комментарий обязателен."""
        user = await UserService(session).block(user_id, data, current_user)

        return cls.present(user, viewer=current_user)

    @classmethod
    @Route.post(
        "/{user_id}/unblock",
        summary="Разблокировка пользователя",
        response=UserRead,
        errors=(
            ForbiddenError,
            NotFoundError,
        ),
    )
    async def unblock(
        cls, user_id: int, data: UnblockRequest, current_user: CurrentUser, session: DatabaseSession
    ) -> UserRead:
        """Разблокирует пользователя; комментарий можно не указывать."""
        user = await UserService(session).unblock(user_id, data, current_user)

        return cls.present(user, viewer=current_user)

    @staticmethod
    @Route.delete(
        "/{user_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Удаление пользователя",
        errors=(
            ForbiddenError,
            NotFoundError,
        ),
    )
    async def delete(user_id: int, current_user: CurrentUser, session: DatabaseSession) -> Response:
        """Мягко удаляет пользователя: свой аккаунт — пользователь, любой — админ."""
        await UserService(session).delete(user_id, current_user)

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @staticmethod
    @Route.get(
        "/{user_id}/roles",
        summary="Роли пользователя",
        response=list[RoleType],
        errors=(
            ForbiddenError,
            NotFoundError,
        ),
    )
    async def roles(
        user_id: int, current_user: CurrentUser, session: DatabaseSession
    ) -> list[RoleType]:
        """Возвращает дополнительные роли пользователя."""
        user = await UserService(session).get(user_id, current_user)

        roles = Access.sorted_roles(user)

        return roles

    @staticmethod
    @Route.put(
        "/{user_id}/roles/{role}",
        summary="Выдача роли",
        response=list[RoleType],
        errors=(
            ForbiddenError,
            NotFoundError,
        ),
    )
    async def grant_role(
        user_id: int, role: RoleType, current_user: CurrentUser, session: DatabaseSession
    ) -> list[RoleType]:
        """Выдаёт роль пользователю; только админ."""
        user = await UserService(session).grant_role(user_id, role, current_user)

        roles = Access.sorted_roles(user)

        return roles

    @staticmethod
    @Route.delete(
        "/{user_id}/roles/{role}",
        summary="Снятие роли",
        response=list[RoleType],
        errors=(
            ForbiddenError,
            NotFoundError,
            ConflictError,
        ),
    )
    async def revoke_role(
        user_id: int, role: RoleType, current_user: CurrentUser, session: DatabaseSession
    ) -> list[RoleType]:
        """Снимает роль с пользователя; только админ, последнего админа лишить роли нельзя."""
        user = await UserService(session).revoke_role(user_id, role, current_user)

        roles = Access.sorted_roles(user)

        return roles
