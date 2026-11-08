from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import (
    CurrentTelegramId,
    CurrentUser,
    DatabaseSession,
    Dependencies,
    PageParams,
)
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


class UsersRouter:
    """Пользователи: регистрация, профиль, блокировка, роли."""

    @staticmethod
    def present(user: User, viewer: User | None) -> UserRead:
        """Комментарий (например, причина блокировки) видят только организаторы и админы."""
        data = UserRead.model_validate(user)

        if viewer is None or not Access.is_staff(viewer):
            return data.model_copy(update={"comment": None})

        return data

    @classmethod
    async def register(cls, data: UserCreate, session: DatabaseSession) -> UserRead:
        """Регистрирует волонтёра; нужно согласие на обработку персональных данных."""
        user = await UserService(session).register(data)

        return cls.present(user, viewer=None)

    @classmethod
    async def get_by_telegram_id(
        cls, telegram_id: int, current_telegram_id: CurrentTelegramId, session: DatabaseSession
    ) -> UserRead:
        """Возвращает пользователя по Telegram ID; чужого — только организатору и админу."""
        user = await UserService(session).get_by_telegram_id(telegram_id, current_telegram_id)

        return cls.present(user, viewer=user if user.telegram_id == current_telegram_id else None)

    @classmethod
    async def get(
        cls, user_id: int, current_user: CurrentUser, session: DatabaseSession
    ) -> UserRead:
        """Возвращает пользователя по ID: свой профиль или любой — организатору и админу."""
        user = await UserService(session).get(user_id, current_user)

        return cls.present(user, viewer=current_user)

    @classmethod
    async def update(
        cls, user_id: int, data: UserUpdate, current_user: CurrentUser, session: DatabaseSession
    ) -> UserRead:
        """Обновляет профиль и настройки уведомлений: свой — пользователь, любой — админ."""
        user = await UserService(session).update(user_id, data, current_user)

        return cls.present(user, viewer=current_user)

    @classmethod
    async def search(
        cls,
        current_user: CurrentUser,
        session: DatabaseSession,
        pagination: PageParams,
        status_: Annotated[UserStatus | None, Query(alias="status")] = None,
        role: RoleType | None = None,
        full_name: Annotated[str | None, Query(max_length=255)] = None,
        phone: Annotated[str | None, Query(max_length=16)] = None,
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
    async def block(
        cls, user_id: int, data: BlockRequest, current_user: CurrentUser, session: DatabaseSession
    ) -> UserRead:
        """Блокирует пользователя; комментарий обязателен."""
        user = await UserService(session).block(user_id, data, current_user)

        return cls.present(user, viewer=current_user)

    @classmethod
    async def unblock(
        cls, user_id: int, data: UnblockRequest, current_user: CurrentUser, session: DatabaseSession
    ) -> UserRead:
        """Разблокирует пользователя; комментарий можно не указывать."""
        user = await UserService(session).unblock(user_id, data, current_user)

        return cls.present(user, viewer=current_user)

    @staticmethod
    async def delete(user_id: int, current_user: CurrentUser, session: DatabaseSession) -> Response:
        """Мягко удаляет пользователя: свой аккаунт — пользователь, любой — админ."""
        await UserService(session).delete(user_id, current_user)

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @staticmethod
    async def roles(
        user_id: int, current_user: CurrentUser, session: DatabaseSession
    ) -> list[RoleType]:
        """Возвращает дополнительные роли пользователя."""
        user = await UserService(session).get(user_id, current_user)

        roles = sorted(Access.roles(user))

        return roles

    @staticmethod
    async def grant_role(
        user_id: int, role: RoleType, current_user: CurrentUser, session: DatabaseSession
    ) -> list[RoleType]:
        """Выдаёт роль пользователю; только админ."""
        user = await UserService(session).grant_role(user_id, role, current_user)

        roles = sorted(Access.roles(user))

        return roles

    @staticmethod
    async def revoke_role(
        user_id: int, role: RoleType, current_user: CurrentUser, session: DatabaseSession
    ) -> list[RoleType]:
        """Снимает роль с пользователя; только админ, последнего админа лишить роли нельзя."""
        user = await UserService(session).revoke_role(user_id, role, current_user)

        roles = sorted(Access.roles(user))

        return roles

    @classmethod
    def build(cls) -> APIRouter:
        """Собирает роутер пользователей; доступ только по токену сервиса."""
        router = APIRouter(
            prefix="/api/users",
            tags=["users"],
            dependencies=[Depends(Dependencies.service)],
        )

        router.add_api_route(
            "", cls.register, methods=["POST"], status_code=status.HTTP_201_CREATED
        )
        router.add_api_route("", cls.search, methods=["GET"])
        router.add_api_route("/by-telegram/{telegram_id}", cls.get_by_telegram_id, methods=["GET"])
        router.add_api_route("/{user_id}", cls.get, methods=["GET"])
        router.add_api_route("/{user_id}", cls.update, methods=["PATCH"])
        router.add_api_route(
            "/{user_id}", cls.delete, methods=["DELETE"], status_code=status.HTTP_204_NO_CONTENT
        )
        router.add_api_route("/{user_id}/block", cls.block, methods=["POST"])
        router.add_api_route("/{user_id}/unblock", cls.unblock, methods=["POST"])
        router.add_api_route("/{user_id}/roles", cls.roles, methods=["GET"])
        router.add_api_route("/{user_id}/roles/{role}", cls.grant_role, methods=["PUT"])
        router.add_api_route("/{user_id}/roles/{role}", cls.revoke_role, methods=["DELETE"])

        return router
