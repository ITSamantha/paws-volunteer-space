from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.handlers.language import LanguageChoice, set_language
from bot.i18n.repository import LocaleRepository
from bot.i18n.translator import Translator

pytestmark = pytest.mark.integration


@pytest.fixture
def locales(sessions: async_sessionmaker[AsyncSession]) -> LocaleRepository:
    return LocaleRepository(sessions)


@pytest.fixture
def translator() -> Translator:
    return Translator("Europe/Moscow")


class TestKeyboard:
    """Кнопки выбора языка."""

    def test_offers_every_supported_language(self) -> None:
        """Предлагаются все поддерживаемые языки, названия — каждое на своём языке."""
        buttons = [b for row in LanguageChoice.keyboard().inline_keyboard for b in row]

        assert [button.text for button in buttons] == ["Русский", "English"]
        assert [button.callback_data for button in buttons] == ["language:ru", "language:en"]

    def test_buttons_match_translator_languages(self) -> None:
        """Список кнопок совпадает с языками переводчика."""
        assert tuple(LanguageChoice.NAMES) == Translator.SUPPORTED


class TestSetLanguage:
    """Нажатие на кнопку выбора языка."""

    @staticmethod
    def pressed(data: str, user_id: int = 1) -> MagicMock:
        callback = MagicMock()
        callback.data = data
        callback.from_user = MagicMock(id=user_id)
        callback.message = MagicMock(spec=Message)
        callback.message.answer = AsyncMock()
        callback.answer = AsyncMock()

        return callback

    async def test_language_is_saved_and_confirmed(
        self, locales: LocaleRepository, translator: Translator
    ) -> None:
        """Выбор сохраняется, подтверждение приходит на выбранном языке."""
        callback = self.pressed("language:en")

        await set_language(callback, locales, translator)

        assert await locales.get(1) == "en"
        assert callback.message.answer.await_args.args[0] == "Language changed: English"
        callback.answer.assert_awaited_once()

    async def test_unknown_code_means_default(
        self, locales: LocaleRepository, translator: Translator
    ) -> None:
        """Подделанный код языка заменяется языком по умолчанию."""
        callback = self.pressed("language:xx")

        await set_language(callback, locales, translator)

        assert await locales.get(1) == "ru"

    async def test_inaccessible_message_is_not_a_problem(
        self, locales: LocaleRepository, translator: Translator
    ) -> None:
        """Если исходное сообщение недоступно, язык всё равно сохраняется."""
        callback = self.pressed("language:en")
        callback.message = None

        await set_language(callback, locales, translator)

        assert await locales.get(1) == "en"
        callback.answer.assert_awaited_once()
