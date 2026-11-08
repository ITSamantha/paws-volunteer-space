from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.database.models import User
from app.database.models.enums import RoleType, UserStatus
from app.repositories.users import UserRepository
from app.schemas.pagination import Pagination
from app.schemas.users import (
    BlockRequest,
    UnblockRequest,
    UserCreate,
    UserFilters,
    UserUpdate,
)
from app.services.access import Access


class UserService:
    """Сценарии работы с пользователями. Права проверяются здесь, а не в роутерах."""

    def __init__(self, session: AsyncSession) -> None:
        """Работает в переданной сессии."""
        self.__session = session
        self.__users = UserRepository(session)

    async def register(self, data: UserCreate) -> User:
        """Регистрирует волонтёра."""
        user = User(**data.model_dump(), roles=[])

        await self.__users.add(user)
        await self.__session.commit()

        return user

    async def get(self, user_id: int, current_user: User) -> User:
        """Возвращает пользователя: себя может любой, остальных — организатор и админ."""
        self.__require_self_or_staff(current_user, user_id)

        user = await self.__require(user_id)

        return user

    async def get_by_telegram_id(self, telegram_id: int, current_telegram_id: int) -> User:
        """Возвращает пользователя по Telegram ID с той же проверкой прав."""
        user = await self.__users.get_by_telegram_id(telegram_id)

        if telegram_id != current_telegram_id:
            current_user = await self.__users.get_by_telegram_id(current_telegram_id)

            if current_user is None or not Access.is_staff(current_user):
                raise ForbiddenError("Недостаточно прав")

        if user is None:
            raise NotFoundError("Пользователь не найден")

        return user

    async def update(self, user_id: int, data: UserUpdate, current_user: User) -> User:
        """Обновляет профиль: себя может любой, остальных — админ."""
        self.__require_self_or_admin(current_user, user_id)
        user = await self.__require(user_id)

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(user, field, value)

        await self.__users.flush()
        await self.__session.commit()

        return user

    async def search(
        self, filters: UserFilters, pagination: Pagination, current_user: User
    ) -> tuple[list[User], int]:
        """Ищет пользователей; доступно организаторам и админам."""
        self.__require_staff(current_user)

        users, total = await self.__users.search(filters, pagination)

        return users, total

    async def block(self, user_id: int, data: BlockRequest, current_user: User) -> User:
        """Блокирует пользователя с обязательным комментарием."""
        user = await self.__require_manageable(user_id, current_user)

        user.status = UserStatus.BLOCKED
        user.comment = data.comment

        await self.__users.flush()
        await self.__session.commit()

        return user

    async def unblock(self, user_id: int, data: UnblockRequest, current_user: User) -> User:
        """Разблокирует пользователя."""
        user = await self.__require_manageable(user_id, current_user)

        user.status = UserStatus.ACTIVE
        user.comment = data.comment

        await self.__users.flush()
        await self.__session.commit()

        return user

    async def delete(self, user_id: int, current_user: User) -> None:
        """Мягко удаляет пользователя."""
        self.__require_self_or_admin(current_user, user_id)
        user = await self.__require(user_id)

        user.deleted_at = datetime.now(UTC)

        await self.__users.flush()
        await self.__session.commit()

    async def grant_role(self, user_id: int, role: RoleType, current_user: User) -> User:
        """Выдаёт роль; только администратор."""
        if not Access.is_admin(current_user):
            raise ForbiddenError("Роли выдаёт только администратор")

        user = await self.__require(user_id)

        if await self.__users.has_role(user.id, role):
            return user

        await self.__users.add_role(user.id, role, current_user.id)
        await self.__session.commit()
        await self.__users.reload_roles(user)

        return user

    async def revoke_role(self, user_id: int, role: RoleType, current_user: User) -> User:
        """Снимает роль; только админ, последнего администратора лишить роли нельзя."""
        if not Access.is_admin(current_user):
            raise ForbiddenError("Роли снимает только администратор")

        user = await self.__require(user_id)

        if role is RoleType.ADMIN and await self.__users.count_admins() <= 1:
            raise ConflictError("Нельзя снять роль с последнего администратора")

        await self.__users.remove_role(user.id, role)
        await self.__session.commit()
        await self.__users.reload_roles(user)

        return user

    async def __require(self, user_id: int) -> User:
        """Возвращает пользователя или выбрасывает NotFoundError."""
        user = await self.__users.get(user_id)

        if user is None:
            raise NotFoundError("Пользователь не найден")

        return user

    async def __require_manageable(self, user_id: int, current_user: User) -> User:
        """Возвращает пользователя, статус которого текущий пользователь вправе менять."""
        self.__require_staff(current_user)

        if user_id == current_user.id:
            raise ForbiddenError("Нельзя менять собственный статус")

        user = await self.__require(user_id)

        if Access.is_admin(user) and not Access.is_admin(current_user):
            raise ForbiddenError("Блокировать администратора может только администратор")

        return user

    @staticmethod
    def __require_staff(current_user: User) -> None:
        """Только организаторы и администраторы."""
        if not Access.is_staff(current_user):
            raise ForbiddenError("Доступно только организаторам и администраторам")

    @staticmethod
    def __require_self_or_staff(current_user: User, user_id: int) -> None:
        """Только сам пользователь, организатор или администратор."""
        if current_user.id != user_id and not Access.is_staff(current_user):
            raise ForbiddenError("Недостаточно прав")

    @staticmethod
    def __require_self_or_admin(current_user: User, user_id: int) -> None:
        """Только сам пользователь или администратор."""
        if current_user.id != user_id and not Access.is_admin(current_user):
            raise ForbiddenError("Недостаточно прав")
