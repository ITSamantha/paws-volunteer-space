import logging
from typing import ClassVar, Protocol

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError

from app.core.config import KafkaSettings
from app.messaging.schemas import NotificationMessage

logger = logging.getLogger(__name__)


class PublishError(Exception):
    """Сообщение не удалось передать брокеру."""


class Publisher(Protocol):
    """Отправитель событий боту."""

    async def publish(self, message: NotificationMessage) -> None:
        """Передаёт событие брокеру и ждёт подтверждения."""


class NullPublisher:
    """Заглушка на случай, когда Kafka выключена: события никуда не уходят."""

    async def publish(self, message: NotificationMessage) -> None:
        """Ничего не отправляет."""
        logger.debug("Kafka выключена, событие %s не отправлено", message.type.value)


class KafkaPublisher:
    """Публикация событий в один топик Kafka.

    Приоритет лежит и в теле, и в заголовке сообщения. Ключ — Telegram ID получателя, поэтому
    события одному человеку идут по порядку.
    """

    def __init__(self, settings: KafkaSettings) -> None:
        """Готовит продюсера; соединение открывается в start()."""
        self.__topic = settings.notifications_topic
        self.__producer = AIOKafkaProducer(
            bootstrap_servers=settings.bootstrap_servers, enable_idempotence=True
        )

    async def start(self) -> None:
        """Подключается к брокеру."""
        await self.__producer.start()

    async def stop(self) -> None:
        """Отключается от брокера."""
        await self.__producer.stop()

    async def publish(self, message: NotificationMessage) -> None:
        """Передаёт событие брокеру и ждёт подтверждения."""
        try:
            await self.__producer.send_and_wait(
                self.__topic,
                value=message.model_dump_json().encode(),
                key=str(message.telegram_id).encode(),
                headers=[("priority", str(message.priority).encode())],
            )
        except KafkaError as error:
            raise PublishError(str(error)) from error


class Publishing:
    """Отправитель событий, общий для всего приложения."""

    __current: ClassVar[Publisher | None] = None

    @classmethod
    def use(cls, publisher: Publisher | None) -> None:
        """Назначает отправителя; None возвращает заглушку."""
        cls.__current = publisher

    @classmethod
    def get(cls) -> Publisher:
        """Текущий отправитель или заглушка."""
        return cls.__current or NullPublisher()
