import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import URL, inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.database.models import Base
from tests.postgres import Migrator, PostgresServer

pytestmark = pytest.mark.integration


async def table_names(url: URL) -> set[str]:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            names = await connection.run_sync(lambda sync: set(inspect(sync).get_table_names()))
    finally:
        await engine.dispose()
    return names - {"alembic_version"}


async def enum_names(url: URL) -> set[str]:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            rows = await connection.execute(text("SELECT typname FROM pg_type WHERE typtype = 'e'"))
    finally:
        await engine.dispose()
    return {row[0] for row in rows}


async def differences(url: URL) -> list[object]:
    def compare(connection: Connection) -> list[object]:
        context = MigrationContext.configure(
            connection, opts={"compare_type": True, "compare_server_default": True}
        )
        return list(compare_metadata(context, Base.metadata))

    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(compare)
    finally:
        await engine.dispose()


class TestInitialSchema:
    """Начальная миграция на настоящей PostgreSQL."""

    async def test_creates_all_model_tables(self, migrated_database_url: URL) -> None:
        """После миграции в БД ровно те таблицы, что описаны в моделях."""
        assert await table_names(migrated_database_url) == set(Base.metadata.tables)

    async def test_matches_models(self, migrated_database_url: URL) -> None:
        """Схема в БД не отличается от моделей (то же самое проверяет alembic check)."""
        assert await differences(migrated_database_url) == []

    async def test_downgrade_removes_tables_and_types(
        self, postgres_server: PostgresServer, migrator: Migrator
    ) -> None:
        """Откат удаляет все таблицы и все enum-типы."""
        url = postgres_server.create_database("downgrade")
        migrator.upgrade(url)

        migrator.downgrade(url)

        assert await table_names(url) == set()
        assert await enum_names(url) == set()

    async def test_can_upgrade_again_after_downgrade(
        self, postgres_server: PostgresServer, migrator: Migrator
    ) -> None:
        """После отката миграцию можно применить повторно."""
        url = postgres_server.create_database("again")
        migrator.upgrade(url)
        migrator.downgrade(url)

        migrator.upgrade(url)

        assert await table_names(url) == set(Base.metadata.tables)
