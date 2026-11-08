from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

import pytest
from sqlalchemy import URL
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from tests.app.database.factory import Factory

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
