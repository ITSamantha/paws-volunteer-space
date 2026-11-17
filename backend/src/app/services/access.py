from typing import ClassVar

from app.core.exceptions import ForbiddenError
from app.database.models import User
from app.database.models.enums import RoleType


class Access:
    """Права пользователя по его ролям. У пользователя должны быть загружены роли."""

    ADMIN_ROLES: ClassVar[frozenset[RoleType]] = frozenset({RoleType.ADMIN})
    STAFF_ROLES: ClassVar[frozenset[RoleType]] = frozenset({RoleType.ADMIN, RoleType.ORGANIZER})
    PUBLISHER_ROLES: ClassVar[frozenset[RoleType]] = frozenset(
        {RoleType.ADMIN, RoleType.ORGANIZER, RoleType.SMM}
    )

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
    def require_staff(cls, user: User) -> None:
        """Допускает только организаторов и администраторов."""
        if not cls.is_staff(user):
            raise ForbiddenError("Доступно только организаторам и администраторам")

    @classmethod
    def require_publisher(cls, user: User) -> None:
        """Допускает администраторов, организаторов и SMM."""
        if not cls.is_publisher(user):
            raise ForbiddenError("Доступно только администраторам, организаторам и SMM")

    @classmethod
    def is_publisher(cls, user: User) -> bool:
        """Пользователь может готовить рассылки."""
        return bool(cls.roles(user) & cls.PUBLISHER_ROLES)

    @classmethod
    def require_admin(cls, user: User) -> None:
        """Допускает только администраторов."""
        if not cls.is_admin(user):
            raise ForbiddenError("Доступно только администраторам")

    @classmethod
    def is_staff(cls, user: User) -> bool:
        """Пользователь — организатор или администратор."""
        return bool(cls.roles(user) & cls.STAFF_ROLES)
