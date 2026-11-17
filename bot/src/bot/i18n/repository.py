from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.queue.models import UserLocale


class LocaleRepository:
    """Хранилище языков пользователей."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        """Работает через переданную фабрику сессий; каждая операция — своя транзакция."""
        self.__sessions = sessions

    async def get(self, telegram_id: int) -> str | None:
        """Сохранённый язык пользователя или None, если он ещё не выбран."""
        async with self.__sessions() as session:
            locale = await session.scalar(
                select(UserLocale.locale).where(UserLocale.telegram_id == telegram_id)
            )

        return locale

    async def set(self, telegram_id: int, locale: str) -> None:
        """Сохраняет язык пользователя, заменяя прежний."""
        statement = insert(UserLocale).values(
            telegram_id=telegram_id, locale=locale, updated_at=datetime.now(UTC)
        )
        statement = statement.on_conflict_do_update(
            index_elements=["telegram_id"],
            set_={"locale": statement.excluded.locale, "updated_at": statement.excluded.updated_at},
        )

        async with self.__sessions() as session, session.begin():
            await session.execute(statement)

    async def set_if_absent(self, telegram_id: int, locale: str) -> str:
        """Запоминает язык, если пользователь ещё не выбирал; возвращает действующий язык."""
        async with self.__sessions() as session, session.begin():
            await session.execute(
                insert(UserLocale)
                .values(telegram_id=telegram_id, locale=locale, updated_at=datetime.now(UTC))
                .on_conflict_do_nothing(index_elements=["telegram_id"])
            )
            current = await session.scalar(
                select(UserLocale.locale).where(UserLocale.telegram_id == telegram_id)
            )

        return current or locale

    async def menu_message_id(self, telegram_id: int) -> int | None:
        """Сообщение с меню, которое бот показывал этому человеку."""
        async with self.__sessions() as session:
            message_id = await session.scalar(
                select(UserLocale.menu_message_id).where(UserLocale.telegram_id == telegram_id)
            )

        return message_id

    async def remember_menu(self, telegram_id: int, message_id: int) -> None:
        """Запоминает сообщение меню, не меняя выбранный язык."""
        statement = insert(UserLocale).values(
            telegram_id=telegram_id,
            locale="ru",
            menu_message_id=message_id,
            updated_at=datetime.now(UTC),
        )
        statement = statement.on_conflict_do_update(
            index_elements=["telegram_id"],
            set_={"menu_message_id": statement.excluded.menu_message_id},
        )

        async with self.__sessions() as session, session.begin():
            await session.execute(statement)
