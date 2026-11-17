import asyncio
import logging
from datetime import timedelta

import httpx
from aiogram import Dispatcher
from sqlalchemy import URL
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from bot.api.client import ApiClient
from bot.config import Settings
from bot.handlers import events, language, menu, mine, start
from bot.i18n.repository import LocaleRepository
from bot.i18n.translator import Translator
from bot.messaging.consumer import NotificationConsumer
from bot.queue.repository import JobRepository
from bot.queue.worker import QueueWorker
from bot.sending.messages import Messages
from bot.sending.sender import TelegramSender

logger = logging.getLogger(__name__)


class Application:
    """Сборка и запуск бота: чтение Kafka, очередь доставки, ответы на команды."""

    @staticmethod
    def create_engine(url: URL) -> AsyncEngine:
        """Движок БД; таблицы создаются миграциями Alembic."""
        return create_async_engine(url, pool_pre_ping=True)

    @classmethod
    async def run(cls) -> None:
        """Запускает все части бота и останавливает их вместе."""
        settings = Settings.get()
        logging.basicConfig(level=settings.app.log_level.upper())

        engine = cls.create_engine(settings.database.url)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        jobs = JobRepository(sessions)
        locales = LocaleRepository(sessions)
        translator = Translator(settings.app.timezone)
        await jobs.purge_finished(timedelta(days=settings.queue.keep_finished_days))

        bot = TelegramSender.create_bot(settings.telegram.bot_token.get_secret_value())
        http = httpx.AsyncClient(base_url=settings.api.base_url, timeout=10)
        api = ApiClient(settings.api.bot_token.get_secret_value(), http)
        worker = QueueWorker(
            jobs, locales, TelegramSender(bot), Messages(translator), settings.queue
        )
        consumer = NotificationConsumer(settings.kafka, jobs)
        dispatcher = Dispatcher(locales=locales, translator=translator, api=api)
        dispatcher.include_router(start.router)
        dispatcher.include_router(events.router)
        dispatcher.include_router(mine.router)
        dispatcher.include_router(menu.router)
        dispatcher.include_router(language.router)

        await consumer.start()
        tasks = [
            asyncio.create_task(consumer.run()),
            asyncio.create_task(worker.run()),
            asyncio.create_task(dispatcher.start_polling(bot)),
        ]

        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
        finally:
            for task in tasks:
                task.cancel()

            outcomes = await asyncio.gather(*tasks, return_exceptions=True)
            await consumer.stop()
            await http.aclose()
            await bot.session.close()
            await engine.dispose()

        failures = [outcome for outcome in outcomes if isinstance(outcome, Exception)]

        if failures:
            raise failures[0]
