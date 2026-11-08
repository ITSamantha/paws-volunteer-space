import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Notification
from app.database.models.enums import NotificationStatus, NotificationType
from tests.app.database.conftest import Rejected
from tests.app.database.factory import Factory

pytestmark = pytest.mark.integration


class TestNotificationInDatabase:
    """Таблица notifications на настоящей БД."""

    async def test_defaults_are_applied(self, session: AsyncSession, factory: Factory) -> None:
        """Новое уведомление ждёт отправки без попыток и ошибок."""
        user = await factory.user()
        notification = Notification(user_id=user.id, type=NotificationType.REMINDER)
        session.add(notification)
        await session.flush()

        assert notification.status is NotificationStatus.PENDING
        assert notification.attempts == 0
        assert notification.scheduled_at is not None
        assert notification.sent_at is None

    async def test_payload_is_stored_as_json(self, session: AsyncSession, factory: Factory) -> None:
        """Данные для шаблона сохраняются как JSON и читаются обратно."""
        user = await factory.user()
        notification = Notification(
            user_id=user.id,
            type=NotificationType.EVENT_CHANGED,
            payload={"fields": ["starts_at"], "count": 1},
        )
        session.add(notification)
        await session.flush()
        await session.refresh(notification)

        assert notification.payload == {"fields": ["starts_at"], "count": 1}

    async def test_same_dedup_key_for_one_user_is_rejected(
        self, session: AsyncSession, factory: Factory, rejected: Rejected
    ) -> None:
        """Одному получателю нельзя создать два уведомления с одним ключом."""
        user = await factory.user()
        session.add(
            Notification(
                user_id=user.id, type=NotificationType.REMINDER, dedup_key="reminder:1:24h"
            )
        )
        await session.flush()

        async with rejected("uq_notifications_user_id_dedup_key"):
            session.add(
                Notification(
                    user_id=user.id, type=NotificationType.REMINDER, dedup_key="reminder:1:24h"
                )
            )

    async def test_same_dedup_key_for_different_users_is_accepted(
        self, session: AsyncSession, factory: Factory
    ) -> None:
        """Один и тот же ключ у разных получателей допустим."""
        first = await factory.user()
        second = await factory.user()

        session.add_all(
            [
                Notification(user_id=first.id, type=NotificationType.REMINDER, dedup_key="k"),
                Notification(user_id=second.id, type=NotificationType.REMINDER, dedup_key="k"),
            ]
        )
        await session.flush()

    async def test_notifications_without_key_do_not_conflict(
        self, session: AsyncSession, factory: Factory
    ) -> None:
        """Уведомления без ключа можно создавать сколько угодно."""
        user = await factory.user()

        session.add_all(
            [Notification(user_id=user.id, type=NotificationType.BROADCAST) for _ in range(3)]
        )
        await session.flush()

    async def test_notifications_are_deleted_with_user(
        self, session: AsyncSession, factory: Factory
    ) -> None:
        """Уведомления удаляются вместе с пользователем."""
        user = await factory.user()
        notification = Notification(user_id=user.id, type=NotificationType.NEW_EVENT)
        session.add(notification)
        await session.flush()

        await session.delete(user)
        await session.flush()

        remaining = await session.scalars(
            select(Notification).where(Notification.user_id == user.id)
        )
        assert remaining.all() == []
