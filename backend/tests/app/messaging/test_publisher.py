from unittest.mock import patch

import pytest
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError

from app.core.config import KafkaSettings
from app.messaging.publisher import KafkaPublisher, NullPublisher, PublishError, Publishing
from tests.app.conftest import FakePublisher
from tests.app.messaging.test_schemas import message


class TestPublishing:
    """Выбор отправителя событий."""

    def test_stub_is_used_when_nothing_is_set(self) -> None:
        """Пока отправитель не назначен, используется заглушка."""
        Publishing.use(None)

        assert isinstance(Publishing.get(), NullPublisher)

    def test_assigned_publisher_is_returned(self) -> None:
        """Назначенный отправитель возвращается, сброс возвращает заглушку."""
        publisher = FakePublisher()

        Publishing.use(publisher)
        try:
            assert Publishing.get() is publisher
        finally:
            Publishing.use(None)

        assert isinstance(Publishing.get(), NullPublisher)

    async def test_stub_accepts_messages_quietly(self) -> None:
        """Заглушка принимает событие и ничего не делает."""
        await NullPublisher().publish(message())


class TestKafkaPublisherErrors:
    """Ошибки отправки в Kafka."""

    async def test_broker_error_becomes_publish_error(self) -> None:
        """Ошибка клиента Kafka превращается в PublishError."""
        publisher = KafkaPublisher(KafkaSettings(_env_file=None))

        with (
            patch.object(AIOKafkaProducer, "send_and_wait", side_effect=KafkaError("недоступен")),
            pytest.raises(PublishError, match="недоступен"),
        ):
            await publisher.publish(message())
