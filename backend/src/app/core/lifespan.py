from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import Settings
from app.database.session import Database
from app.messaging.publisher import KafkaPublisher, Publishing


class Lifespan:
    """Жизненный цикл приложения: подключение к Kafka и освобождение ресурсов."""

    @staticmethod
    @asynccontextmanager
    async def run(_: FastAPI) -> AsyncIterator[None]:
        """Работа приложения.

        Если включён Kafka, подключает отправителя событий для бота. При остановке закрывает
        соединения.
        """
        settings = Settings.get().kafka
        publisher = KafkaPublisher(settings) if settings.is_enabled else None

        if publisher is not None:
            await publisher.start()
            Publishing.use(publisher)

        yield

        if publisher is not None:
            Publishing.use(None)
            await publisher.stop()

        await Database.engine().dispose()
