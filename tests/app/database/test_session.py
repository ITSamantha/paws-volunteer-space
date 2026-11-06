from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import Database


class TestDatabase:
    """Подключение к БД."""

    def test_engine_is_cached(self) -> None:
        """Движок создаётся один раз на процесс."""
        assert Database.engine() is Database.engine()

    def test_engine_uses_asyncpg(self) -> None:
        """Движок асинхронный и работает через asyncpg."""
        assert Database.engine().dialect.driver == "asyncpg"

    def test_session_factory_is_cached(self) -> None:
        """Фабрика сессий создаётся один раз."""
        assert Database.session_factory() is Database.session_factory()

    def test_session_factory_keeps_objects_loaded_after_commit(self) -> None:
        """После коммита объекты не протухают: в async-коде это вызвало бы лишние запросы."""
        assert Database.session_factory().kw["expire_on_commit"] is False

    async def test_session_yields_async_session(self) -> None:
        """Зависимость отдаёт асинхронную сессию и закрывает её после использования."""
        generator = Database.session()

        session = await anext(generator)

        assert isinstance(session, AsyncSession)
        await generator.aclose()
