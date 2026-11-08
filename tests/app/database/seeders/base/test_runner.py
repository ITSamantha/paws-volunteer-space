import runpy
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import URL, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.database.models import Bonus, Tag
from app.database.seeders import BonusSeeder, Seeders, TagSeeder
from app.main import app
from tests.postgres import Migrator, PostgresServer


class TestSeeders:
    """Запуск сидеров."""

    def test_main_runs_all_seeders(self) -> None:
        """Точка входа запускает сидеры один раз."""
        with patch.object(Seeders, "run", new=AsyncMock()) as run:
            Seeders.main()

        run.assert_awaited_once()

    def test_module_entrypoint_calls_main(self) -> None:
        """python -m app.database.seeders запускает сидеры."""
        with patch.object(Seeders, "main") as main:
            runpy.run_module("app.database.seeders", run_name="__main__")

        main.assert_called_once()

    def test_application_module_exposes_app(self) -> None:
        """Модуль app.main отдаёт готовое приложение для uvicorn."""
        assert app.title == "Paw Volunteer Space"


@pytest.mark.integration
class TestSeedersRunInDatabase:
    """Запуск сидеров на настоящей БД."""

    @pytest.fixture
    async def seeded_engine(
        self, postgres_server: PostgresServer, migrator: Migrator
    ) -> AsyncEngine:
        url: URL = postgres_server.create_database("seeders")
        migrator.upgrade(url)
        return create_async_engine(url, poolclass=NullPool)

    async def test_run_commits_all_dictionaries(self, seeded_engine: AsyncEngine) -> None:
        """Полный запуск сохраняет значения всех справочников."""
        database = MagicMock()
        database.session_factory.return_value = async_sessionmaker(seeded_engine)
        database.engine.return_value = seeded_engine

        with patch("app.database.seeders.base.runner.Database", database):
            await Seeders.run()

        engine = create_async_engine(seeded_engine.url, poolclass=NullPool)
        async_factory = async_sessionmaker(engine)
        async with async_factory() as session:
            bonuses = await session.scalar(select(func.count()).select_from(Bonus))
            tags = await session.scalar(select(func.count()).select_from(Tag))
        await engine.dispose()

        assert bonuses == len(BonusSeeder.titles())
        assert tags == len(TagSeeder.titles())
