import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.enums import NotificationType
from app.messaging.publisher import PublishError, Publishing
from app.messaging.schemas import NotificationMessage
from app.services.notifications import NotificationService
from tests.app.conftest import FakePublisher
from tests.app.database.factory import Factory

pytestmark = pytest.mark.integration


class FailingPublisher:
    """Не принимает указанные по счёту сообщения."""

    def __init__(self, fail_on: set[int], error: Exception) -> None:
        self.fail_on = fail_on
        self.error = error
        self.messages: list[NotificationMessage] = []
        self.attempts = 0

    async def publish(self, message: NotificationMessage) -> None:
        self.attempts += 1

        if self.attempts in self.fail_on:
            raise self.error

        self.messages.append(message)


class TestStaging:
    """События копятся до коммита."""

    async def test_nothing_is_sent_before_commit(
        self, session: AsyncSession, factory: Factory, published: FakePublisher
    ) -> None:
        """Пока изменения не сохранены, бот ничего не получает."""
        user = await factory.user()
        service = NotificationService(session)

        service.add([user.id], NotificationType.REGISTRATION_CONFIRMED, 1, {"a": 1})

        assert published.messages == []

    async def test_commit_sends_events_with_all_fields(
        self, session: AsyncSession, factory: Factory, published: FakePublisher
    ) -> None:
        """После коммита уходит сообщение с получателем, приоритетом, временем и ключом."""
        user = await factory.user(telegram_id=4242)
        send_at = datetime.now(UTC) + timedelta(days=1)
        service = NotificationService(session)
        service.add(
            [user.id], NotificationType.REMINDER, 7, {"title": "Выезд"}, send_at, "reminder:7"
        )

        await service.commit()

        (message,) = published.messages
        assert message.telegram_id == 4242
        assert message.type is NotificationType.REMINDER
        assert message.priority == NotificationType.REMINDER.priority
        assert message.event_id == 7
        assert message.payload == {"title": "Выезд"}
        assert message.send_at == send_at
        assert message.key == "reminder:7"

    async def test_urgent_type_has_high_priority(
        self, session: AsyncSession, factory: Factory, published: FakePublisher
    ) -> None:
        """Приоритет определяется типом события."""
        user = await factory.user()
        service = NotificationService(session)
        service.add([user.id], NotificationType.EVENT_CANCELLED, None, {})
        service.add([user.id], NotificationType.BROADCAST, None, {})

        await service.commit()

        assert [m.priority for m in published.messages] == [1, 3]

    async def test_every_recipient_gets_a_message(
        self, session: AsyncSession, factory: Factory, published: FakePublisher
    ) -> None:
        """Каждому получателю уходит своё сообщение, повторы получателей схлопываются."""
        first, second = await factory.user(), await factory.user()
        service = NotificationService(session)
        service.add([first.id, second.id, first.id], NotificationType.SPOT_FREED, None, {})

        await service.commit()

        assert sorted(m.telegram_id for m in published.messages) == sorted(
            [first.telegram_id, second.telegram_id]
        )

    async def test_no_recipients_means_nothing_to_send(
        self, session: AsyncSession, published: FakePublisher
    ) -> None:
        """Событие без получателей не создаётся."""
        service = NotificationService(session)
        service.add([], NotificationType.SPOT_FREED, None, {})

        await service.commit()

        assert published.messages == []

    async def test_events_are_sent_once(
        self, session: AsyncSession, factory: Factory, published: FakePublisher
    ) -> None:
        """Повторный commit или send не дублирует уже отправленное."""
        user = await factory.user()
        service = NotificationService(session)
        service.add([user.id], NotificationType.SPOT_FREED, None, {})

        await service.commit()
        await service.commit()
        await service.send()

        assert len(published.messages) == 1

    async def test_discard_drops_staged_events(
        self, session: AsyncSession, factory: Factory, published: FakePublisher
    ) -> None:
        """Отброшенные события не отправляются."""
        user = await factory.user()
        service = NotificationService(session)
        service.add([user.id], NotificationType.SPOT_FREED, None, {})

        service.discard()
        await service.commit()

        assert published.messages == []


class TestTransactions:
    """События зависят от успеха транзакции."""

    async def test_failed_commit_rolls_back_and_sends_nothing(
        self, session: AsyncSession, factory: Factory, published: FakePublisher
    ) -> None:
        """Если коммит не удался, сессия откатывается, события отбрасываются, ошибка идёт наружу."""
        user = await factory.user()
        service = NotificationService(session)
        service.add([user.id], NotificationType.SPOT_FREED, None, {})
        failure = OperationalError("COMMIT", {}, Exception("соединение потеряно"))

        with (
            patch.object(session, "commit", side_effect=failure),
            patch.object(session, "rollback") as rollback,
            pytest.raises(OperationalError),
        ):
            await service.commit()

        rollback.assert_awaited_once()
        assert published.messages == []

    async def test_events_of_failed_commit_are_not_sent_later(
        self, session: AsyncSession, factory: Factory, published: FakePublisher
    ) -> None:
        """Отброшенные при сбое события не уходят и при следующем commit."""
        user = await factory.user()
        service = NotificationService(session)
        service.add([user.id], NotificationType.SPOT_FREED, None, {})
        failure = OperationalError("COMMIT", {}, Exception("сбой"))

        with (
            patch.object(session, "commit", side_effect=failure),
            patch.object(session, "rollback"),
            pytest.raises(OperationalError),
        ):
            await service.commit()

        await service.commit()

        assert published.messages == []


class TestFailures:
    """Сбои отправки не ломают запрос."""

    @pytest.mark.parametrize("error", [PublishError("брокер недоступен"), RuntimeError("сбой")])
    async def test_publish_failure_does_not_break_the_request(
        self,
        session: AsyncSession,
        factory: Factory,
        caplog: pytest.LogCaptureFixture,
        error: Exception,
    ) -> None:
        """Ошибка брокера записывается в лог, commit завершается нормально."""
        user = await factory.user()
        publisher = FailingPublisher({1}, error)
        Publishing.use(publisher)
        service = NotificationService(session)
        service.add([user.id], NotificationType.SPOT_FREED, None, {})

        try:
            with caplog.at_level(logging.ERROR):
                await service.commit()
        finally:
            Publishing.use(None)

        assert publisher.messages == []
        assert "не отправлено боту" in caplog.text

    async def test_one_failure_does_not_stop_the_rest(
        self, session: AsyncSession, factory: Factory
    ) -> None:
        """Сбой одного сообщения не мешает остальным."""
        users = [await factory.user() for _ in range(3)]
        publisher = FailingPublisher({2}, PublishError("сбой"))
        Publishing.use(publisher)
        service = NotificationService(session)
        service.add([user.id for user in users], NotificationType.SPOT_FREED, None, {})

        try:
            await service.commit()
        finally:
            Publishing.use(None)

        assert publisher.attempts == 3
        assert [m.telegram_id for m in publisher.messages] == [
            users[0].telegram_id,
            users[2].telegram_id,
        ]

    async def test_unknown_recipient_is_skipped(
        self,
        session: AsyncSession,
        factory: Factory,
        published: FakePublisher,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Получатель, которого нет в БД, пропускается, остальные получают сообщение."""
        user = await factory.user()
        service = NotificationService(session)
        service.add([999999, user.id], NotificationType.SPOT_FREED, None, {})

        with caplog.at_level(logging.WARNING):
            await service.commit()

        assert [m.telegram_id for m in published.messages] == [user.telegram_id]
        assert "999999" in caplog.text

    async def test_lookup_failure_does_not_break_the_request(
        self,
        session: AsyncSession,
        factory: Factory,
        published: FakePublisher,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Если не удалось найти получателей, запрос всё равно успешен."""
        user = await factory.user()
        service = NotificationService(session)
        service.add([user.id], NotificationType.SPOT_FREED, None, {})

        failure = OperationalError("SELECT", {}, Exception("сбой"))

        with (
            patch.object(session, "execute", side_effect=failure),
            caplog.at_level(logging.ERROR),
        ):
            await service.send()

        assert published.messages == []
        assert "получателей" in caplog.text

    async def test_without_kafka_events_are_dropped_quietly(
        self, session: AsyncSession, factory: Factory
    ) -> None:
        """Когда Kafka выключена, события тихо отбрасываются."""
        Publishing.use(None)
        user = await factory.user()
        service = NotificationService(session)
        service.add([user.id], NotificationType.SPOT_FREED, None, {})

        await service.commit()
