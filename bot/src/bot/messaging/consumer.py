import asyncio
import logging

from aiokafka import AIOKafkaConsumer
from pydantic import ValidationError

from bot.config import KafkaSettings
from bot.messaging.schemas import NotificationMessage
from bot.queue.repository import JobRepository

logger = logging.getLogger(__name__)


class NotificationConsumer:
    """Читает события из Kafka и кладёт их в очередь доставки.

    Чтение подтверждается только после того, как событие надёжно сохранено в очереди: если бот
    упадёт, Kafka отдаст событие снова, а повтор отбросят по id. Непонятные сообщения
    пропускаются, чтобы не блокировать остальные.
    """

    def __init__(
        self, settings: KafkaSettings, jobs: JobRepository, retry_pause: float = 1.0
    ) -> None:
        """Готовит потребителя; соединение открывается в start()."""
        self.__jobs = jobs
        self.__retry_pause = retry_pause
        self.__consumer = AIOKafkaConsumer(
            settings.notifications_topic,
            bootstrap_servers=settings.bootstrap_servers,
            group_id=settings.group_id,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
        )

    async def start(self) -> None:
        """Подключается к брокеру."""
        await self.__consumer.start()

    async def stop(self) -> None:
        """Отключается от брокера."""
        await self.__consumer.stop()

    async def run(self) -> None:
        """Бесконечный цикл чтения."""
        async for record in self.__consumer:
            await self.__handle(record.value or b"")
            await self.__consumer.commit()

    async def __handle(self, raw: bytes) -> None:
        """Сохраняет событие в очереди; при сбое хранилища повторяет, пока не получится."""
        try:
            message = NotificationMessage.model_validate_json(raw)
        except ValidationError:
            logger.exception("Непонятное сообщение пропущено")
            return

        while True:
            try:
                await self.__jobs.add(message)
                return
            except Exception:
                logger.exception("Не удалось сохранить событие %s, повтор", message.id)
                await asyncio.sleep(self.__retry_pause)
