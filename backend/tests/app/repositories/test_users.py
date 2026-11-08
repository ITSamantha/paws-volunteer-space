import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError
from app.database.models import User
from app.database.models.enums import RoleType
from app.repositories.users import UserRepository
from tests.app.database.factory import Factory

pytestmark = pytest.mark.integration


class TestUserRepository:
    """Доступ к пользователям на настоящей БД."""

    async def test_duplicate_telegram_id_becomes_conflict(
        self, session: AsyncSession, factory: Factory
    ) -> None:
        """Нарушение уникальности Telegram ID превращается в понятную ошибку."""
        existing = await factory.user()

        with pytest.raises(ConflictError):
            await UserRepository(session).add(
                User(telegram_id=existing.telegram_id, phone="+79990000001")
            )

    async def test_other_integrity_errors_are_not_hidden(self, session: AsyncSession) -> None:
        """Остальные нарушения ограничений не маскируются под конфликт."""
        with pytest.raises(IntegrityError):
            await UserRepository(session).add(User(telegram_id=1, phone="не телефон"))

    async def test_role_rule_violation_becomes_forbidden(
        self, session: AsyncSession, factory: Factory
    ) -> None:
        """Нарушение правила выдачи ролей на уровне БД превращается в отказ в доступе."""
        await factory.role(await factory.user(), RoleType.ADMIN)
        outsider = await factory.user()

        with pytest.raises(ForbiddenError):
            await UserRepository(session).add_role(outsider.id, RoleType.ORGANIZER, outsider.id)

    async def test_failed_insert_leaves_session_usable(
        self, session: AsyncSession, factory: Factory
    ) -> None:
        """После неудачной вставки сессия остаётся рабочей."""
        existing = await factory.user()
        repository = UserRepository(session)
        with pytest.raises(ConflictError):
            await repository.add(User(telegram_id=existing.telegram_id, phone="+79990000001"))

        await repository.add(User(telegram_id=999_999, phone="+79990000002"))

        assert await repository.get_by_telegram_id(999_999) is not None

    async def test_unrelated_role_errors_are_not_hidden(
        self, session: AsyncSession, factory: Factory
    ) -> None:
        """Прочие ошибки при выдаче роли, например несуществующий пользователь, не маскируются."""
        granter = await factory.user()

        with pytest.raises(IntegrityError):
            await UserRepository(session).add_role(999_999, RoleType.SMM, granter.id)
