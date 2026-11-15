from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI

from app.core.config import KafkaSettings
from app.core.lifespan import Lifespan
from app.messaging.publisher import NullPublisher, Publishing


class TestLifespan:
    """Жизненный цикл приложения."""

    async def test_engine_is_disposed_on_shutdown(self) -> None:
        """При остановке приложения соединения с БД закрываются."""
        with patch("app.core.lifespan.Database.engine") as engine:
            engine.return_value.dispose = AsyncMock()

            async with Lifespan.run(FastAPI()):
                engine.return_value.dispose.assert_not_called()

            engine.return_value.dispose.assert_awaited_once()

    async def test_kafka_publisher_is_connected_when_enabled(self) -> None:
        """Если Kafka включена, на время работы приложения подключается отправитель событий."""
        publisher = MagicMock(start=AsyncMock(), stop=AsyncMock())
        settings = MagicMock(kafka=KafkaSettings(is_enabled=True, _env_file=None))

        with (
            patch("app.core.lifespan.Settings.get", return_value=settings),
            patch("app.core.lifespan.KafkaPublisher", return_value=publisher),
            patch("app.core.lifespan.Database.engine") as engine,
        ):
            engine.return_value.dispose = AsyncMock()

            async with Lifespan.run(FastAPI()):
                publisher.start.assert_awaited_once()
                assert Publishing.get() is publisher

            publisher.stop.assert_awaited_once()
            assert isinstance(Publishing.get(), NullPublisher)

    async def test_no_publisher_when_kafka_is_disabled(self) -> None:
        """Если Kafka выключена, отправитель не создаётся."""
        settings = MagicMock(kafka=KafkaSettings(is_enabled=False, _env_file=None))

        with (
            patch("app.core.lifespan.Settings.get", return_value=settings),
            patch("app.core.lifespan.KafkaPublisher") as factory,
            patch("app.core.lifespan.Database.engine") as engine,
        ):
            engine.return_value.dispose = AsyncMock()

            async with Lifespan.run(FastAPI()):
                pass

        factory.assert_not_called()
