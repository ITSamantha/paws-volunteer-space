from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.database.session import Database
from app.main import create_app


class HealthySession:
    async def execute(self, *args: Any, **kwargs: Any) -> None:
        return None


class BrokenSession:
    async def execute(self, *args: Any, **kwargs: Any) -> None:
        raise OperationalError("SELECT 1", {}, Exception("host=db.internal user=secret_user"))


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def healthy_database(app: FastAPI) -> None:
    async def override() -> AsyncIterator[HealthySession]:
        yield HealthySession()

    app.dependency_overrides[Database.session] = override


@pytest.fixture
def broken_database(app: FastAPI) -> None:
    async def override() -> AsyncIterator[BrokenSession]:
        yield BrokenSession()

    app.dependency_overrides[Database.session] = override
