import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.database.models.enums import UserStatus
from tests.app.database.conftest import Rejected
from tests.app.database.factory import Factory

pytestmark = pytest.mark.integration


class TestUserInDatabase:
    """Таблица users на настоящей БД."""

    async def test_defaults_are_applied(self, factory: Factory) -> None:
        """Новый пользователь активен, уведомления включены, согласия на обработку данных нет."""
        user = await factory.user()

        assert user.status is UserStatus.ACTIVE
        assert user.has_notifications_enabled is True
        assert user.is_data_processing_allowed is False
        assert user.created_at is not None
        assert user.deleted_at is None

    @pytest.mark.parametrize("phone", ["+79991234567", "+12345678901", "+123456789012345"])
    async def test_valid_phone_is_accepted(self, factory: Factory, phone: str) -> None:
        """Телефон в международном формате принимается."""
        user = await factory.user(phone=phone)

        assert user.phone == phone

    @pytest.mark.parametrize("phone", ["89991234567", "+7 999 123 45 67", "+123456789", "+7abc"])
    async def test_invalid_phone_is_rejected(
        self, session: AsyncSession, rejected: Rejected, phone: str
    ) -> None:
        """Телефон не в формате +<10–15 цифр> отклоняется."""
        async with rejected("ck_users_phone_format"):
            session.add(User(telegram_id=1, phone=phone))

    async def test_block_without_comment_is_rejected(
        self, session: AsyncSession, rejected: Rejected
    ) -> None:
        """Заблокировать пользователя без причины нельзя."""
        async with rejected("ck_users_blocked_requires_comment"):
            session.add(
                User(telegram_id=1, phone="+79990000000", status=UserStatus.BLOCKED, comment="  ")
            )

    async def test_block_with_comment_is_accepted(self, factory: Factory) -> None:
        """Блокировка с причиной принимается."""
        user = await factory.user(status=UserStatus.BLOCKED, comment="Нарушение правил")

        assert user.status is UserStatus.BLOCKED

    async def test_telegram_id_is_unique(
        self, session: AsyncSession, factory: Factory, rejected: Rejected
    ) -> None:
        """Два пользователя с одним Telegram ID невозможны."""
        user = await factory.user()

        async with rejected("uq_users_telegram_id"):
            session.add(User(telegram_id=user.telegram_id, phone="+79990000001"))

    async def test_isu_id_is_unique(
        self, session: AsyncSession, factory: Factory, rejected: Rejected
    ) -> None:
        """Номер ИСУ уникален, но у разных пользователей может быть пустым."""
        await factory.user(isu_id="123456")
        await factory.user()
        await factory.user()

        async with rejected("uq_users_isu_id"):
            session.add(User(telegram_id=1, phone="+79990000001", isu_id="123456"))

    async def test_phone_is_not_unique(self, factory: Factory) -> None:
        """Один номер телефона может быть у нескольких пользователей."""
        first = await factory.user(phone="+79990000005")
        second = await factory.user(phone="+79990000005")

        assert first.id != second.id
