from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import URL, text
from sqlalchemy.ext.asyncio import AsyncEngine

from bot.app import Application
from bot.config import (
    AppSettings,
    DatabaseSettings,
    KafkaSettings,
    QueueSettings,
    Settings,
    TelegramSettings,
)


class TestApplication:
    """Сборка и запуск бота."""

    def test_engine_pings_connections(self) -> None:
        """Движок проверяет соединение перед использованием: рестарт БД не ломает бота."""
        url = URL.create("postgresql+asyncpg", "u", "p", "localhost", 5432, "d")

        engine = Application.create_engine(url)

        assert engine.pool._pre_ping is True

    @pytest.mark.integration
    async def test_engine_works_with_the_database(self, engine: AsyncEngine) -> None:
        """Подключение к базе работает."""
        async with engine.connect() as connection:
            assert (await connection.execute(text("SELECT 1"))).scalar_one() == 1

    async def test_run_starts_everything_and_stops_cleanly(self) -> None:
        """Запуск поднимает чтение Kafka, воркер и опрос Telegram, остановка закрывает всё."""
        settings = Settings(
            app=AppSettings(_env_file=None),
            telegram=TelegramSettings(_env_file=None, bot_token="123456:test-token-0123456789"),
            kafka=KafkaSettings(_env_file=None),
            database=DatabaseSettings(_env_file=None, db="d", user="u", password="p"),
            queue=QueueSettings(_env_file=None),
        )
        consumer = MagicMock(start=AsyncMock(), stop=AsyncMock(), run=AsyncMock())
        bot = MagicMock(session=MagicMock(close=AsyncMock()))
        engine = MagicMock(dispose=AsyncMock())
        dispatcher = MagicMock(start_polling=AsyncMock(side_effect=RuntimeError("остановка")))
        jobs = MagicMock(purge_finished=AsyncMock(), requeue_stuck=AsyncMock())

        with (
            patch("bot.app.Settings.get", return_value=settings),
            patch("bot.app.NotificationConsumer", return_value=consumer),
            patch("bot.app.TelegramSender.create_bot", return_value=bot),
            patch("bot.app.Application.create_engine", return_value=engine),
            patch("bot.app.Dispatcher", return_value=dispatcher),
            patch("bot.app.JobRepository", return_value=jobs),
            patch("bot.app.LocaleRepository"),
            patch("bot.app.async_sessionmaker"),
            patch("bot.app.QueueWorker") as worker,
        ):
            worker.return_value.run = AsyncMock()

            with pytest.raises(RuntimeError, match="остановка"):
                await Application.run()

        consumer.start.assert_awaited_once()
        consumer.stop.assert_awaited_once()
        jobs.purge_finished.assert_awaited_once()
        assert dispatcher.include_router.call_count == 5
        dispatcher.start_polling.assert_awaited_once_with(bot)
        bot.session.close.assert_awaited_once()
        engine.dispose.assert_awaited_once()

    async def test_run_ends_quietly_when_every_part_finishes(self) -> None:
        """Если все части завершились без ошибок, запуск тоже завершается без ошибок."""
        settings = Settings(
            app=AppSettings(_env_file=None),
            telegram=TelegramSettings(_env_file=None, bot_token="123456:test-token-0123456789"),
            kafka=KafkaSettings(_env_file=None),
            database=DatabaseSettings(_env_file=None, db="d", user="u", password="p"),
            queue=QueueSettings(_env_file=None),
        )
        consumer = MagicMock(start=AsyncMock(), stop=AsyncMock(), run=AsyncMock())
        bot = MagicMock(session=MagicMock(close=AsyncMock()))
        engine = MagicMock(dispose=AsyncMock())
        dispatcher = MagicMock(start_polling=AsyncMock())
        jobs = MagicMock(purge_finished=AsyncMock())

        with (
            patch("bot.app.Settings.get", return_value=settings),
            patch("bot.app.NotificationConsumer", return_value=consumer),
            patch("bot.app.TelegramSender.create_bot", return_value=bot),
            patch("bot.app.Application.create_engine", return_value=engine),
            patch("bot.app.Dispatcher", return_value=dispatcher),
            patch("bot.app.JobRepository", return_value=jobs),
            patch("bot.app.LocaleRepository"),
            patch("bot.app.async_sessionmaker"),
            patch("bot.app.QueueWorker") as worker,
        ):
            worker.return_value.run = AsyncMock()

            await Application.run()

        consumer.stop.assert_awaited_once()
        engine.dispose.assert_awaited_once()
