from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import URL
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.application import Application
from app.core.config import Settings
from app.database.session import Database
from tests.app.database.factory import Factory


class HealthySession:
    async def execute(self, *args: Any, **kwargs: Any) -> None:
        return None


class BrokenSession:
    async def execute(self, *args: Any, **kwargs: Any) -> None:
        raise OperationalError("SELECT 1", {}, Exception("host=db.internal user=secret_user"))


@pytest.fixture
def app() -> FastAPI:
    return Application.create()


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


Rejected = Callable[[str], AbstractAsyncContextManager[None]]


@pytest.fixture
async def engine(migrated_database_url: URL) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(migrated_database_url, poolclass=NullPool)

    yield engine

    await engine.dispose()


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Сессия в транзакции, которая откатывается после теста: тесты не влияют друг на друга."""
    async with engine.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        ) as session:
            yield session

        await transaction.rollback()


@pytest.fixture
def rejected(session: AsyncSession) -> Rejected:
    """Ожидание отказа БД: внутри блока действие должно нарушить ограничение с этим именем."""

    @asynccontextmanager
    async def expect(fragment: str) -> AsyncIterator[None]:
        message = ""

        try:
            async with session.begin_nested():
                yield
                await session.flush()
        except IntegrityError as error:
            message = str(error)

        assert fragment in message, f"БД не отклонила действие, ожидалось нарушение {fragment}"

    return expect


@pytest.fixture
def factory(session: AsyncSession) -> Factory:
    return Factory(session)


@pytest.fixture
async def api(app: FastAPI, session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """HTTP-клиент к приложению, работающему на сессии теста (изменения откатываются)."""

    async def override() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[Database.session] = override

    token = Settings.get().auth.bot_token.get_secret_value()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        yield client
