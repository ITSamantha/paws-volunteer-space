from typing import ClassVar

from app.database.models import User
from app.database.models.enums import RoleType


class Access:
    """Права пользователя по его ролям. У пользователя должны быть загружены роли."""

    ADMIN_ROLES: ClassVar[frozenset[RoleType]] = frozenset({RoleType.ADMIN})
    STAFF_ROLES: ClassVar[frozenset[RoleType]] = frozenset({RoleType.ADMIN, RoleType.ORGANIZER})

    @staticmethod
    def roles(user: User) -> set[RoleType]:
        """Дополнительные роли пользователя."""
        return {granted.role for granted in user.roles}

    @classmethod
    def sorted_roles(cls, user: User) -> list[RoleType]:
        """Дополнительные роли пользователя в стабильном порядке."""
        roles = sorted(cls.roles(user))

        return roles

    @classmethod
    def is_admin(cls, user: User) -> bool:
        """Пользователь — администратор."""
        return bool(cls.roles(user) & cls.ADMIN_ROLES)

    @classmethod
    def is_staff(cls, user: User) -> bool:
        """Пользователь — организатор или администратор."""
        return bool(cls.roles(user) & cls.STAFF_ROLES)
