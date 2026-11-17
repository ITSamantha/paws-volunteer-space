import os
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import URL, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from bot.app import Application
from bot.messaging.schemas import NotificationMessage, NotificationType
from bot.queue.repository import JobRepository
from tests.kafka import KafkaServer
from tests.postgres import Migrator, PostgresServer

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:test-token-0123456789")
os.environ.setdefault("AUTH_BOT_TOKEN", "test-bot-token-with-32-characters")
os.environ.setdefault("POSTGRES_DB", "test")
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")


@pytest.fixture(scope="session")
def kafka_server() -> Iterator[KafkaServer]:
    server = KafkaServer()

    try:
        server.start()
    except Exception as error:
        pytest.skip(f"Docker недоступен, проверки с Kafka пропущены: {error}")

    yield server

    server.stop()


@pytest.fixture(scope="session")
def postgres_server() -> Iterator[PostgresServer]:
    server = PostgresServer()

    try:
        server.start()
    except Exception as error:
        pytest.skip(f"Docker недоступен, проверки с PostgreSQL пропущены: {error}")

    yield server

    server.stop()


@pytest.fixture(scope="session")
def migrator() -> Migrator:
    return Migrator()


@pytest.fixture(scope="session")
def migrated_database_url(postgres_server: PostgresServer, migrator: Migrator) -> URL:
    url = postgres_server.create_database("migrated")

    migrator.upgrade(url)

    return url


@pytest.fixture
async def engine(migrated_database_url: URL) -> AsyncIterator[AsyncEngine]:
    engine = Application.create_engine(migrated_database_url)

    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE notification_jobs, user_locales RESTART IDENTITY"))

    yield engine

    await engine.dispose()


@pytest.fixture
def sessions(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
def jobs(sessions: async_sessionmaker[AsyncSession]) -> JobRepository:
    return JobRepository(sessions)


def make_message(**fields: Any) -> NotificationMessage:
    values: dict[str, Any] = {
        "id": uuid4().hex,
        "type": NotificationType.REGISTRATION_CONFIRMED,
        "priority": 2,
        "telegram_id": 100,
        "event_id": 5,
        "payload": {"title": "Выезд"},
        "created_at": datetime.now(UTC),
    }

    return NotificationMessage.model_validate({**values, **fields})
