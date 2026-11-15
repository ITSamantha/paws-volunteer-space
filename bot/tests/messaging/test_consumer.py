import asyncio
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from aiokafka import AIOKafkaProducer

from bot.config import KafkaSettings
from bot.messaging.consumer import NotificationConsumer
from bot.messaging.schemas import NotificationMessage
from bot.queue.repository import JobRepository
from tests.conftest import make_message
from tests.kafka import KafkaServer
from tests.support import wait_until

pytestmark = pytest.mark.integration


@pytest.fixture
async def settings(kafka_server: KafkaServer) -> KafkaSettings:
    configured = KafkaSettings(
        _env_file=None,
        bootstrap_servers=kafka_server.bootstrap_servers,
        notifications_topic=f"notifications-{uuid4().hex[:10]}",
        group_id=f"bot-{uuid4().hex[:8]}",
    )
    await kafka_server.create_topics(configured.notifications_topic)

    return configured


@pytest.fixture
async def producer(settings: KafkaSettings) -> AsyncIterator[AIOKafkaProducer]:
    """Публикует события так же, как это делает API."""
    producer = AIOKafkaProducer(bootstrap_servers=settings.bootstrap_servers)
    await producer.start()

    yield producer

    await producer.stop()


async def send(producer: AIOKafkaProducer, topic: str, raw: bytes) -> None:
    await producer.send_and_wait(topic, raw)


class TestNotificationConsumer:
    """Чтение событий из настоящей Kafka."""

    async def test_event_lands_in_the_queue(
        self, settings: KafkaSettings, producer: AIOKafkaProducer, jobs: JobRepository
    ) -> None:
        """Событие из Kafka попадает в очередь доставки."""
        message = make_message(telegram_id=321)
        consumer = NotificationConsumer(settings, jobs)
        await consumer.start()
        task = asyncio.create_task(consumer.run())

        try:
            await send(producer, settings.notifications_topic, message.model_dump_json().encode())
            await wait_until(lambda: self.has_job(jobs, 321))
        finally:
            task.cancel()
            await consumer.stop()

        (job,) = await jobs.waiting(321)
        assert job.message_id == message.id

    @staticmethod
    async def has_job(jobs: JobRepository, telegram_id: int) -> bool:
        return len(await jobs.waiting(telegram_id)) > 0

    async def test_garbage_is_skipped_and_does_not_block(
        self, settings: KafkaSettings, producer: AIOKafkaProducer, jobs: JobRepository
    ) -> None:
        """Непонятное сообщение пропускается, следующие читаются."""
        good = make_message(telegram_id=322)
        consumer = NotificationConsumer(settings, jobs)
        await consumer.start()
        task = asyncio.create_task(consumer.run())

        try:
            await send(producer, settings.notifications_topic, b"not json")
            await send(producer, settings.notifications_topic, b'{"id": 1}')
            await send(producer, settings.notifications_topic, good.model_dump_json().encode())
            await wait_until(lambda: self.has_job(jobs, 322))
        finally:
            task.cancel()
            await consumer.stop()

        assert len(await jobs.waiting(322)) == 1

    async def test_duplicate_delivery_creates_one_job(
        self, settings: KafkaSettings, producer: AIOKafkaProducer, jobs: JobRepository
    ) -> None:
        """Если Kafka доставила событие дважды, задание одно."""
        message = make_message(telegram_id=323)
        payload = message.model_dump_json().encode()
        consumer = NotificationConsumer(settings, jobs)
        await consumer.start()
        task = asyncio.create_task(consumer.run())

        try:
            await send(producer, settings.notifications_topic, payload)
            await send(producer, settings.notifications_topic, payload)
            marker = make_message(telegram_id=324)
            await send(producer, settings.notifications_topic, marker.model_dump_json().encode())
            await wait_until(lambda: self.has_job(jobs, 324))
        finally:
            task.cancel()
            await consumer.stop()

        assert len(await jobs.waiting(323)) == 1

    async def test_storage_failure_is_retried_until_saved(
        self, settings: KafkaSettings, producer: AIOKafkaProducer, jobs: JobRepository
    ) -> None:
        """Пока очередь недоступна, событие не теряется: сохранение повторяется."""
        message = make_message(telegram_id=325)
        consumer = NotificationConsumer(settings, jobs, retry_pause=0.01)
        original = jobs.add
        attempts = 0

        async def flaky(item: NotificationMessage) -> bool:
            nonlocal attempts
            attempts += 1

            if attempts < 3:
                raise ConnectionError("БД недоступна")

            added = await original(item)

            return added

        await consumer.start()
        with patch.object(jobs, "add", side_effect=flaky):
            task = asyncio.create_task(consumer.run())

            try:
                await send(
                    producer, settings.notifications_topic, message.model_dump_json().encode()
                )
                await wait_until(lambda: self.has_job(jobs, 325))
            finally:
                task.cancel()
                await consumer.stop()

        assert attempts == 3

    async def test_processed_events_are_not_read_again(
        self, settings: KafkaSettings, producer: AIOKafkaProducer, jobs: JobRepository
    ) -> None:
        """Прочитанное и сохранённое подтверждено: после перезапуска оно не приходит снова."""
        first = make_message(telegram_id=326)
        await send(producer, settings.notifications_topic, first.model_dump_json().encode())
        consumer = NotificationConsumer(settings, jobs)
        await consumer.start()
        task = asyncio.create_task(consumer.run())
        await wait_until(lambda: self.has_job(jobs, 326))
        task.cancel()
        await consumer.stop()

        spy = AsyncMock(wraps=jobs.add)
        restarted = NotificationConsumer(settings, jobs)
        await restarted.start()
        with patch.object(jobs, "add", spy):
            task = asyncio.create_task(restarted.run())

            try:
                second = make_message(telegram_id=327)
                await send(
                    producer, settings.notifications_topic, second.model_dump_json().encode()
                )
                await wait_until(lambda: self.has_job(jobs, 327))
            finally:
                task.cancel()
                await restarted.stop()

        assert [call.args[0].id for call in spy.await_args_list] == [second.id]
