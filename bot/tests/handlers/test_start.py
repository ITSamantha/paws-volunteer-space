from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.api.client import ApiClient
from bot.handlers.start import start
from bot.i18n.repository import LocaleRepository
from bot.i18n.translator import Translator

pytestmark = pytest.mark.integration


@pytest.fixture
def locales(sessions: async_sessionmaker[AsyncSession]) -> LocaleRepository:
    return LocaleRepository(sessions)


@pytest.fixture
def translator() -> Translator:
    return Translator("Europe/Moscow")


def incoming(user_id: int = 1, language_code: str | None = "ru") -> MagicMock:
    message = MagicMock(spec=Message)
    message.from_user = MagicMock(id=user_id, language_code=language_code)
    message.answer = AsyncMock()

    return message


def answered(message: MagicMock) -> str:
    return str(message.answer.await_args.args[0])


def api(roles: list[str] | None) -> ApiClient:
    client = MagicMock(spec=ApiClient)
    profile = None if roles is None else MagicMock(roles=roles)
    client.profile = AsyncMock(return_value=profile)

    return client


class TestStart:
    """Команда /start."""

    async def test_greets_in_the_telegram_language(
        self, locales: LocaleRepository, translator: Translator
    ) -> None:
        """Бот здоровается на языке из настроек Telegram и запоминает его."""
        message = incoming(language_code="en-US")

        await start(message, locales, translator, api(None))

        assert "Helping Paws" in answered(message)
        assert await locales.get(1) == "en"

    async def test_unknown_language_means_russian(
        self, locales: LocaleRepository, translator: Translator
    ) -> None:
        """Для неизвестного языка выбирается русский."""
        message = incoming(language_code="de")

        await start(message, locales, translator, api(None))

        assert "Лапки помощи" in answered(message)
        assert await locales.get(1) == "ru"

    async def test_chosen_language_is_kept(
        self, locales: LocaleRepository, translator: Translator
    ) -> None:
        """Ранее выбранный язык важнее языка Telegram."""
        await locales.set(1, "ru")
        message = incoming(language_code="en")

        await start(message, locales, translator, api(None))

        assert "Лапки помощи" in answered(message)

    async def test_message_without_sender_is_ignored(
        self, locales: LocaleRepository, translator: Translator
    ) -> None:
        """Сообщение без отправителя (например, из канала) игнорируется."""
        message = incoming()
        message.from_user = None

        await start(message, locales, translator, api(None))

        message.answer.assert_not_awaited()
