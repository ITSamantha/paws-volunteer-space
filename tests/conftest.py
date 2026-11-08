import os
from collections.abc import Iterator

import pytest
from sqlalchemy import URL

from tests.postgres import Migrator, PostgresServer

os.environ.setdefault("POSTGRES_DB", "test")
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")


@pytest.fixture(scope="session")
def postgres_server() -> Iterator[PostgresServer]:
    server = PostgresServer()
    try:
        server.start()
    except Exception as error:
        pytest.skip(f"Docker недоступен, проверки на реальной БД пропущены: {error}")
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
