from typing import ClassVar, NoReturn

from sqlalchemy import Select, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, ForbiddenError
from app.database.models import User, UserRole
from app.database.models.enums import RoleType
from app.schemas.pagination import Pagination
from app.schemas.users import UserFilters


class UserRepository:
    """Доступ к пользователям и их ролям. Мягко удалённые пользователи не возвращаются."""

    UNIQUE_VIOLATIONS: ClassVar[dict[str, str]] = {
        "uq_users_telegram_id": "Пользователь с таким Telegram ID уже зарегистрирован",
        "uq_users_isu_id": "Пользователь с таким номером ИСУ уже зарегистрирован",
        "uq_users_volunteer_id": "Пользователь с таким ID на добро.рф уже зарегистрирован",
    }
    ROLE_RULE_VIOLATION: ClassVar[str] = "Роли admin и organizer может выдать только администратор"

    def __init__(self, session: AsyncSession) -> None:
        """Работает в переданной сессии."""
        self.__session = session

    async def get(self, user_id: int) -> User | None:
        """Находит пользователя по ID."""
        user = await self.__session.scalar(self.__select().where(User.id == user_id))

        return user

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        """Находит пользователя по Telegram ID."""
        statement = self.__select().where(User.telegram_id == telegram_id)
        user = await self.__session.scalar(statement)

        return user

    async def add(self, user: User) -> None:
        """Добавляет пользователя; нарушение уникальности превращается в ConflictError."""
        try:
            async with self.__session.begin_nested():
                self.__session.add(user)
                await self.__session.flush()
        except IntegrityError as error:
            self.__raise_conflict(error)

    async def flush(self) -> None:
        """Записывает изменения; нарушение уникальности превращается в понятную ошибку."""
        try:
            async with self.__session.begin_nested():
                await self.__session.flush()
        except IntegrityError as error:
            self.__raise_conflict(error)

    async def search(self, filters: UserFilters, pagination: Pagination) -> tuple[list[User], int]:
        """Ищет по фильтрам; возвращает страницу и общее число найденных."""
        conditions = []

        if filters.status is not None:
            conditions.append(User.status == filters.status)

        if filters.role is not None:
            with_role = select(UserRole.user_id).where(UserRole.role == filters.role)
            conditions.append(User.id.in_(with_role))

        if filters.full_name:
            conditions.append(User.full_name.icontains(filters.full_name, autoescape=True))

        if filters.phone:
            conditions.append(User.phone.contains(filters.phone, autoescape=True))

        total = await self.__session.scalar(
            select(func.count()).select_from(User).where(User.deleted_at.is_(None), *conditions)
        )
        statement = (
            self.__select()
            .where(*conditions)
            .order_by(User.created_at.desc(), User.id.desc())
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        users = await self.__session.scalars(statement)

        return list(users), total or 0

    async def count_admins(self) -> int:
        """Число администраторов."""
        statement = (
            select(func.count()).select_from(UserRole).where(UserRole.role == RoleType.ADMIN)
        )

        total = await self.__session.scalar(statement)

        return total or 0

    async def has_role(self, user_id: int, role: RoleType) -> bool:
        """Есть ли у пользователя роль."""
        statement = select(UserRole).where(UserRole.user_id == user_id, UserRole.role == role)

        user_role = await self.__session.scalar(statement)

        return user_role is not None

    async def add_role(self, user_id: int, role: RoleType, granted_by: int) -> None:
        """Выдаёт роль; запрет на уровне БД превращается в ForbiddenError."""
        try:
            async with self.__session.begin_nested():
                self.__session.add(UserRole(user_id=user_id, role=role, granted_by=granted_by))
                await self.__session.flush()
        except IntegrityError as error:
            if self.ROLE_RULE_VIOLATION in str(error.orig):
                raise ForbiddenError(self.ROLE_RULE_VIOLATION) from None

            raise

    async def remove_role(self, user_id: int, role: RoleType) -> None:
        """Снимает роль."""
        await self.__session.execute(
            delete(UserRole).where(UserRole.user_id == user_id, UserRole.role == role)
        )

    async def reload_roles(self, user: User) -> None:
        """Перечитывает роли пользователя из БД."""
        await self.__session.refresh(user, ["roles"])

    @classmethod
    def __raise_conflict(cls, error: IntegrityError) -> NoReturn:
        """Превращает нарушение уникальности в ConflictError с понятным текстом."""
        for constraint, message in cls.UNIQUE_VIOLATIONS.items():
            if constraint in str(error.orig):
                raise ConflictError(message) from None

        raise error

    def __select(self) -> Select[User]:
        """Базовый запрос: не удалённые пользователи с загруженными ролями."""
        return (
            select(User)
            .where(User.deleted_at.is_(None))
            .options(selectinload(User.roles))
            .execution_options(populate_existing=True)
        )
