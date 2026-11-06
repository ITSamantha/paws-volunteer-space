from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings


class Database:
    """Подключение к БД: один движок на процесс и сессия на каждый запрос."""

    @classmethod
    @lru_cache
    def engine(cls) -> AsyncEngine:
        settings = Settings.get()
        return create_async_engine(
            settings.database.url,
            echo=settings.app.is_debug_enabled,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=10,
        )

    @classmethod
    @lru_cache
    def session_factory(cls) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(cls.engine(), expire_on_commit=False)

    @classmethod
    async def session(cls) -> AsyncGenerator[AsyncSession]:
        """Зависимость FastAPI: одна сессия на запрос, коммит выполняет вызывающий код."""
        async with cls.session_factory()() as session:
            yield session
