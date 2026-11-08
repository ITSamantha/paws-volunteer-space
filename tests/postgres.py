import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from sqlalchemy import URL
from testcontainers.community.postgres import PostgresContainer

from app.core.config import Settings

ROOT = Path(__file__).resolve().parent.parent


class PostgresServer:
    """PostgreSQL в контейнере: на каждую проверку создаётся отдельная база."""

    USER = "test"
    PASSWORD = "test"
    ADMIN_DATABASE = "test"

    def __init__(self) -> None:
        self._container = PostgresContainer(
            "postgres:17",
            username=self.USER,
            password=self.PASSWORD,
            dbname=self.ADMIN_DATABASE,
            driver=None,
        )

    def start(self) -> None:
        self._container.start()

    def stop(self) -> None:
        self._container.stop()

    def create_database(self, name: str) -> URL:
        self._container.exec(
            ["psql", "-U", self.USER, "-d", self.ADMIN_DATABASE, "-c", f'CREATE DATABASE "{name}"']
        )

        return self.url(name)

    def url(self, database: str) -> URL:
        return URL.create(
            "postgresql+asyncpg",
            username=self.USER,
            password=self.PASSWORD,
            host=self._container.get_container_host_ip(),
            port=int(self._container.get_exposed_port(5432)),
            database=database,
        )


class Migrator:
    """Запуск миграций Alembic на конкретной базе."""

    def upgrade(self, url: URL, revision: str = "head") -> None:
        self._run(url, lambda config: command.upgrade(config, revision))

    def downgrade(self, url: URL, revision: str = "base") -> None:
        self._run(url, lambda config: command.downgrade(config, revision))

    def _run(self, url: URL, action: Callable[[Config], None]) -> None:
        environment = {
            "POSTGRES_HOST": str(url.host),
            "POSTGRES_PORT": str(url.port),
            "POSTGRES_DB": str(url.database),
            "POSTGRES_USER": str(url.username),
            "POSTGRES_PASSWORD": str(url.password),
        }

        with patch.dict(os.environ, environment):
            Settings.get.cache_clear()

            try:
                config = Config(str(ROOT / "alembic.ini"))

                with ThreadPoolExecutor(max_workers=1) as executor:
                    executor.submit(action, config).result()
            finally:
                Settings.get.cache_clear()
