import asyncio

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import URL, inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from bot.queue.models import Base
from tests.postgres import Migrator, PostgresServer

pytestmark = pytest.mark.integration


async def tables(url: URL) -> set[str]:
    engine = create_async_engine(url, poolclass=NullPool)

    try:
        async with engine.connect() as connection:
            names = await connection.run_sync(lambda sync: set(inspect(sync).get_table_names()))
    finally:
        await engine.dispose()

    return names


async def differences(url: URL) -> list[object]:
    def compare(connection: Connection) -> list[object]:
        context = MigrationContext.configure(
            connection,
            opts={
                "compare_type": True,
                "compare_server_default": True,
                "include_object": lambda obj, name, type_, reflected, compare_to: (
                    not (type_ == "table" and reflected) or name in Base.metadata.tables
                ),
            },
        )

        return list(compare_metadata(context, Base.metadata))

    engine = create_async_engine(url, poolclass=NullPool)

    try:
        async with engine.connect() as connection:
            found = await connection.run_sync(compare)
    finally:
        await engine.dispose()

    return found


class TestMigrations:
    """Миграции бота."""

    def test_upgrade_and_downgrade(
        self, postgres_server: PostgresServer, migrator: Migrator
    ) -> None:
        """Миграция создаёт таблицу очереди и откатывается полностью."""
        url = postgres_server.create_database("bot_migration")

        migrator.upgrade(url)
        created = asyncio.run(tables(url))
        migrator.downgrade(url)
        left = asyncio.run(tables(url))

        assert {"notification_jobs", "user_locales"} <= created
        assert not {"notification_jobs", "user_locales"} & left

    def test_models_match_migration(
        self, postgres_server: PostgresServer, migrator: Migrator
    ) -> None:
        """Модель и миграция не расходятся: autogenerate не находит отличий."""
        url = postgres_server.create_database("bot_drift")

        migrator.upgrade(url)

        assert asyncio.run(differences(url)) == []

    def test_does_not_touch_foreign_tables(
        self, postgres_server: PostgresServer, migrator: Migrator
    ) -> None:
        """База общая с API: чужие таблицы бот не трогает, версии у него отдельные."""
        url = postgres_server.create_database("bot_shared")

        async def prepare() -> None:
            engine = create_async_engine(url, poolclass=NullPool)

            async with engine.begin() as connection:
                await connection.execute(text("CREATE TABLE users (id integer PRIMARY KEY)"))
                await connection.execute(
                    text("CREATE TABLE alembic_version (version_num varchar(32) NOT NULL)")
                )

            await engine.dispose()

        asyncio.run(prepare())
        migrator.upgrade(url)
        migrator.downgrade(url)
        left = asyncio.run(tables(url))

        assert {"users", "alembic_version"} <= left
        assert not {"notification_jobs", "user_locales"} & left
