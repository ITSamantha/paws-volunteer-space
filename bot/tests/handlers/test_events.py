from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.api.client import ApiError, EventLine, EventPage
from bot.handlers.events import back_to_menu, event_card_is_next, show_events
from bot.handlers.menu import Menu
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


def opened(data: str) -> MagicMock:
    callback = MagicMock(spec=CallbackQuery)
    callback.data = data
    callback.from_user = MagicMock(id=1)
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()

    return callback


def page(*events: EventLine) -> EventPage:
    return EventPage(items=list(events), total=len(events))


class TestEventList:
    """Список выездов в том же сообщении."""

    async def test_events_replace_the_menu(
        self, locales: LocaleRepository, translator: Translator
    ) -> None:
        """Кнопка «Мероприятия» показывает выезды и не пишет новое сообщение."""
        await locales.set(1, "ru")
        callback = opened(Menu.EVENTS)
        client = api(None)
        client.events = AsyncMock(
            return_value=page(
                EventLine(
                    id=4,
                    title="Выезд в приют",
                    starts_at=datetime(2030, 3, 5, tzinfo=UTC),
                    occupied=1,
                    capacity=5,
                )
            )
        )

        await show_events(callback, locales, translator, client)

        text = callback.message.edit_text.await_args.args[0]
        labels = [
            button.text
            for row in callback.message.edit_text.await_args.kwargs["reply_markup"].inline_keyboard
            for button in row
        ]
        assert "Куда можно поехать" in text
        assert labels == ["🐾 Выезд в приют · 4", "← В меню"]
        callback.answer.assert_awaited_once()

    async def test_empty_list_says_there_are_no_visits(
        self, locales: LocaleRepository, translator: Translator
    ) -> None:
        """Пустой список честно говорит, что выездов пока нет."""
        callback = opened(Menu.EVENTS)
        client = api(None)
        client.events = AsyncMock(return_value=page())

        await show_events(callback, locales, translator, client)

        assert "нет предстоящих" in callback.message.edit_text.await_args.args[0]

    async def test_api_error_stays_in_the_same_message(
        self, locales: LocaleRepository, translator: Translator
    ) -> None:
        """Сбой API не добавляет сообщение: в меню написано, что список не открылся."""
        callback = opened(Menu.EVENTS)
        client = api(None)
        client.events = AsyncMock(side_effect=ApiError(401, "unauthorized"))

        await show_events(callback, locales, translator, client)

        assert "Не получилось открыть" in callback.message.edit_text.await_args.args[0]

    async def test_back_returns_the_greeting(
        self, locales: LocaleRepository, translator: Translator
    ) -> None:
        """Кнопка «В меню» возвращает приветствие в то же сообщение."""
        await locales.set(1, "en")
        callback = opened("menu:back")

        await back_to_menu(callback, locales, translator, api(["organizer"]))

        text = callback.message.edit_text.await_args.args[0]
        labels = [
            button.text
            for row in callback.message.edit_text.await_args.kwargs["reply_markup"].inline_keyboard
            for button in row
        ]
        assert text.startswith("Hi!")
        assert "🗂 For organizers" in labels

    async def test_opening_an_event_says_the_card_is_next(
        self, locales: LocaleRepository, translator: Translator
    ) -> None:
        """Нажатие на выезд не пишет новое сообщение: карточка ещё впереди."""
        await locales.set(1, "en")
        callback = opened("event:4")

        await event_card_is_next(callback, locales, translator)

        callback.answer.assert_awaited_once_with("The visit card is coming next.")
