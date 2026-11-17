from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.handlers.menu import Menu, section_is_next
from bot.handlers.start import start
from bot.i18n.repository import LocaleRepository
from bot.i18n.translator import Translator
from tests.handlers.test_start import api, incoming

pytestmark = pytest.mark.integration


@pytest.fixture
def locales(sessions: async_sessionmaker[AsyncSession]) -> LocaleRepository:
    return LocaleRepository(sessions)


@pytest.fixture
def translator() -> Translator:
    return Translator("Europe/Moscow")


def labels(markup: InlineKeyboardMarkup) -> list[str]:
    return [button.text for row in markup.inline_keyboard for button in row]


class TestMenu:
    """Главное меню."""

    async def test_volunteer_sees_events_and_language(
        self, locales: LocaleRepository, translator: Translator
    ) -> None:
        """Волонтёр видит мероприятия, свои записи и языки, но не раздел организатора."""
        message = incoming(language_code="en")

        await start(message, locales, translator, api(None))

        keyboard = message.answer.await_args.kwargs["reply_markup"]
        assert labels(keyboard) == ["Events", "My registrations", "Русский", "English"]

    async def test_organizer_gets_an_extra_button(
        self, locales: LocaleRepository, translator: Translator
    ) -> None:
        """Организатор, администратор и SMM видят кнопку своего раздела."""
        message = incoming()

        await start(message, locales, translator, api(["smm"]))

        keyboard = message.answer.await_args.kwargs["reply_markup"]
        assert "Организатору" in labels(keyboard)

    async def test_unfinished_section_says_it_is_next(
        self, locales: LocaleRepository, translator: Translator
    ) -> None:
        """Нажатие на ещё не сделанный раздел объясняет, что он следующий."""
        await locales.set(1, "en")
        callback = MagicMock(spec=CallbackQuery)
        callback.data = Menu.EVENTS
        callback.from_user = MagicMock(id=1)
        callback.answer = AsyncMock()

        await section_is_next(callback, locales, translator)

        callback.answer.assert_awaited_once_with("This section is coming next.")
