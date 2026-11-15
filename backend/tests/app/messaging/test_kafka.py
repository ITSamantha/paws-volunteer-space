import json
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from aiokafka import AIOKafkaConsumer

from app.core.config import KafkaSettings
from app.messaging.publisher import KafkaPublisher
from tests.app.messaging.test_schemas import message
from tests.kafka import KafkaServer

pytestmark = pytest.mark.integration


@pytest.fixture
async def settings(kafka_server: KafkaServer) -> KafkaSettings:
    configured = KafkaSettings(
        is_enabled=True,
        bootstrap_servers=kafka_server.bootstrap_servers,
        notifications_topic=f"notifications-{uuid4().hex[:10]}",
    )
    await kafka_server.create_topics(configured.notifications_topic)

    return configured


@pytest.fixture
async def bot_consumer(settings: KafkaSettings) -> AsyncIterator[AIOKafkaConsumer]:
    """Читает события так же, как это делает бот."""
    consumer = AIOKafkaConsumer(
        settings.notifications_topic,
        bootstrap_servers=settings.bootstrap_servers,
        group_id=f"bot-{uuid4().hex[:8]}",
        auto_offset_reset="earliest",
    )
    await consumer.start()

    yield consumer

    await consumer.stop()


class TestKafkaPublisher:
    """Публикация событий в настоящую Kafka."""

    async def test_bot_receives_json_with_key_and_priority(
        self, settings: KafkaSettings, bot_consumer: AIOKafkaConsumer
    ) -> None:
        """Бот получает JSON; ключ — Telegram ID, приоритет лежит и в теле, и в заголовке."""
        publisher = KafkaPublisher(settings)
        await publisher.start()

        try:
            await publisher.publish(message(telegram_id=4242, priority=1))
        finally:
            await publisher.stop()

        record = await bot_consumer.getone()
        body = json.loads(record.value or b"")
        assert record.key == b"4242"
        assert dict(record.headers)["priority"] == b"1"
        assert body["type"] == "spot_freed"
        assert body["priority"] == 1
        assert body["telegram_id"] == 4242
        assert body["send_at"] is None

    async def test_all_priorities_go_to_one_topic_in_order(
        self, settings: KafkaSettings, bot_consumer: AIOKafkaConsumer
    ) -> None:
        """События любых приоритетов идут в один топик, порядок отправки сохраняется."""
        publisher = KafkaPublisher(settings)
        await publisher.start()

        try:
            for priority in (3, 1, 2):
                await publisher.publish(message(telegram_id=1, priority=priority))
        finally:
            await publisher.stop()

        records = [await bot_consumer.getone() for _ in range(3)]
        assert [json.loads(r.value or b"")["priority"] for r in records] == [3, 1, 2]
