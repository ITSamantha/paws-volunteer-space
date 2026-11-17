from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.api.client import ApiError, OwnRegistration, OwnVisit
from bot.handlers.menu import Menu
from bot.handlers.mine import ask_reason, confirm_cancel, show_mine
from bot.i18n.repository import LocaleRepository
from bot.i18n.translator import Translator
from tests.handlers.test_start import api

pytestmark = pytest.mark.integration


@pytest.fixture
def locales(sessions: async_sessionmaker[AsyncSession]) -> LocaleRepository:
    return LocaleRepository(sessions)


@pytest.fixture
def translator() -> Translator:
    return Translator("Europe/Moscow")


def opened() -> MagicMock:
    callback = MagicMock(spec=CallbackQuery)
    callback.data = Menu.MINE
    callback.from_user = MagicMock(id=1)
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()

    return callback


class TestMyRegistrations:
    """Свои записи в том же сообщении."""

    async def test_lists_visits_and_their_status(
        self, locales: LocaleRepository, translator: Translator
    ) -> None:
        """Кнопка показывает выезды и статус записи, не добавляя сообщение."""
        await locales.set(1, "ru")
        callback = opened()
        client = api(None)
        client.own_registrations = AsyncMock(
            return_value=[
                OwnRegistration(
                    id=1,
                    status="registered",
                    event=OwnVisit(
                        id=4, title="Выезд в приют", starts_at=datetime(2030, 3, 5, 7, tzinfo=UTC)
                    ),
                )
            ]
        )

        await show_mine(callback, locales, translator, client)

        text = callback.message.edit_text.await_args.args[0]
        assert "Ваши записи" in text
        assert "Выезд в приют" in text
        assert "вы записаны" in text
        labels = [
            button.text
            for row in callback.message.edit_text.await_args.kwargs["reply_markup"].inline_keyboard
            for button in row
        ]
        assert "Отменить: Выезд в приют" in labels

    async def test_empty_list_invites_to_choose_a_visit(
        self, locales: LocaleRepository, translator: Translator
    ) -> None:
        """Без записей бот предлагает открыть мероприятия."""
        callback = opened()
        client = api(None)
        client.own_registrations = AsyncMock(return_value=[])

        await show_mine(callback, locales, translator, client)

        assert "никуда не записаны" in callback.message.edit_text.await_args.args[0]

    async def test_api_error_stays_in_the_same_message(
        self, locales: LocaleRepository, translator: Translator
    ) -> None:
        """Сбой API не пишет новое сообщение."""
        callback = opened()
        client = api(None)
        client.own_registrations = AsyncMock(side_effect=ApiError(401, "unauthorized"))

        await show_mine(callback, locales, translator, client)

        assert "Не получилось открыть" in callback.message.edit_text.await_args.args[0]

    async def test_cancel_asks_for_a_ready_reason(
        self, locales: LocaleRepository, translator: Translator
    ) -> None:
        """Отмена предлагает причины кнопками и не просит печатать текст."""
        await locales.set(1, "ru")
        callback = opened()
        callback.data = "cancel:4"

        await ask_reason(callback, locales, translator)

        labels = [
            button.text
            for row in callback.message.edit_text.await_args.kwargs["reply_markup"].inline_keyboard
            for button in row
        ]
        assert callback.message.edit_text.await_args.args[0].startswith("Почему отменяете")
        assert "Не смогу прийти" in labels

    async def test_chosen_reason_cancels_in_the_same_message(
        self, locales: LocaleRepository, translator: Translator
    ) -> None:
        """Выбранная причина уходит в API, итог остаётся в том же сообщении."""
        await locales.set(1, "ru")
        callback = opened()
        callback.data = "reason:4:plans"
        client = api(None)
        client.cancel = AsyncMock()

        await confirm_cancel(callback, locales, translator, client)

        client.cancel.assert_awaited_once_with(1, 4, "Не смогу прийти")
        assert "Запись отменена" in callback.message.edit_text.await_args.args[0]
