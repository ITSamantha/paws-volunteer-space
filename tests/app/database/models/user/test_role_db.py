import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import UserRole
from app.database.models.enums import RoleType
from tests.app.database.conftest import Rejected
from tests.app.database.factory import Factory

pytestmark = pytest.mark.integration

TRIGGER = "Роли admin и organizer может выдать только администратор"


class TestRoleGrantingRules:
    """Правило выдачи ролей (триггер trg_user_roles_check_granter)."""

    async def test_first_admin_can_grant_himself(self, factory: Factory) -> None:
        """Пока в системе нет администраторов, первый может выдать роль самому себе."""
        user = await factory.user()

        role = await factory.role(user, RoleType.ADMIN)

        assert role.role is RoleType.ADMIN

    async def test_second_admin_cannot_grant_himself(
        self, session: AsyncSession, factory: Factory, rejected: Rejected
    ) -> None:
        """Когда администратор уже есть, самовыдача роли admin невозможна."""
        await factory.role(await factory.user(), RoleType.ADMIN)
        outsider = await factory.user()

        async with rejected(TRIGGER):
            session.add(UserRole(user_id=outsider.id, role=RoleType.ADMIN, granted_by=outsider.id))

    async def test_admin_can_grant_admin_and_organizer(self, factory: Factory) -> None:
        """Администратор выдаёт роли admin и organizer."""
        admin = await factory.user()
        await factory.role(admin, RoleType.ADMIN)

        second_admin = await factory.role(await factory.user(), RoleType.ADMIN, admin)
        organizer = await factory.role(await factory.user(), RoleType.ORGANIZER, admin)

        assert second_admin.granted_by == admin.id
        assert organizer.role is RoleType.ORGANIZER

    async def test_organizer_cannot_grant_organizer(
        self, session: AsyncSession, factory: Factory, rejected: Rejected
    ) -> None:
        """Организатор не может выдавать роли organizer."""
        admin = await factory.user()
        await factory.role(admin, RoleType.ADMIN)
        organizer = await factory.user()
        await factory.role(organizer, RoleType.ORGANIZER, admin)
        candidate = await factory.user()

        async with rejected(TRIGGER):
            session.add(
                UserRole(user_id=candidate.id, role=RoleType.ORGANIZER, granted_by=organizer.id)
            )

    async def test_organizer_cannot_grant_admin(
        self, session: AsyncSession, factory: Factory, rejected: Rejected
    ) -> None:
        """Организатор не может выдать роль admin."""
        admin = await factory.user()
        await factory.role(admin, RoleType.ADMIN)
        organizer = await factory.user()
        await factory.role(organizer, RoleType.ORGANIZER, admin)
        candidate = await factory.user()

        async with rejected(TRIGGER):
            session.add(
                UserRole(user_id=candidate.id, role=RoleType.ADMIN, granted_by=organizer.id)
            )

    async def test_anyone_can_grant_smm(self, factory: Factory) -> None:
        """Роль smm не требует прав администратора."""
        author = await factory.user()
        target = await factory.user()

        role = await factory.role(target, RoleType.SMM, author)

        assert role.role is RoleType.SMM

    async def test_role_cannot_be_granted_twice(
        self, session: AsyncSession, factory: Factory, rejected: Rejected
    ) -> None:
        """Одну и ту же роль одному пользователю нельзя выдать дважды."""
        user = await factory.user()
        await factory.role(user, RoleType.SMM)

        async with rejected("pk_user_roles"):
            session.add(UserRole(user_id=user.id, role=RoleType.SMM, granted_by=user.id))

    async def test_changing_role_to_admin_is_checked_too(
        self, session: AsyncSession, factory: Factory, rejected: Rejected
    ) -> None:
        """Повысить smm до admin в обход правила нельзя."""
        await factory.role(await factory.user(), RoleType.ADMIN)
        user = await factory.user()
        role = await factory.role(user, RoleType.SMM)

        async with rejected(TRIGGER):
            role.role = RoleType.ADMIN


class TestRoleRelations:
    """Связи таблицы user_roles."""

    async def test_roles_are_deleted_with_user(
        self, session: AsyncSession, factory: Factory
    ) -> None:
        """При удалении пользователя его роли удаляются."""
        author = await factory.user()
        user = await factory.user()
        await factory.role(user, RoleType.SMM, author)

        await session.delete(user)
        await session.flush()

        assert (
            await session.scalars(select(UserRole).where(UserRole.user_id == user.id))
        ).all() == []

    async def test_granter_with_roles_cannot_be_deleted(
        self, session: AsyncSession, factory: Factory, rejected: Rejected
    ) -> None:
        """Нельзя удалить пользователя, который выдал роли."""
        author = await factory.user()
        await factory.role(await factory.user(), RoleType.SMM, author)

        async with rejected("fk_user_roles_granted_by_users"):
            await session.delete(author)
