from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.api.client import (
    ApiError,
    EventCard,
    EventLine,
    EventPage,
    EventPlace,
    RegistrationResult,
)
from bot.handlers.events import back_to_menu, join_event, show_event, show_events
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

    async def test_opening_an_event_shows_its_card(
        self, locales: LocaleRepository, translator: Translator
    ) -> None:
        """Нажатие на выезд показывает карточку в том же сообщении."""
        await locales.set(1, "ru")
        callback = opened("event:4")
        client = api(None)
        client.event = AsyncMock(
            return_value=EventCard(
                id=4,
                title="Выезд в приют",
                starts_at=datetime(2030, 3, 5, 7, tzinfo=UTC),
                location=None,
                shelter=EventPlace(title="Лапка", address="У метро"),
                capacity=5,
                occupied=1,
                instructions="Сменная обувь",
                status="planned",
            )
        )

        await show_event(callback, locales, translator, client)

        text = callback.message.edit_text.await_args.args[0]
        assert "Выезд в приют" in text
        assert "У метро" in text
        assert "4 из 5" in text
        assert "Сменная обувь" in text
        labels = [
            button.text
            for row in callback.message.edit_text.await_args.kwargs["reply_markup"].inline_keyboard
            for button in row
        ]
        assert labels == ["💛 Записаться", "← К списку", "← В меню"]

    async def test_a_broken_event_button_does_nothing(
        self, locales: LocaleRepository, translator: Translator
    ) -> None:
        """Кнопка без номера выезда не обращается к API."""
        callback = opened("event:")
        client = api(None)
        client.event = AsyncMock()

        await show_event(callback, locales, translator, client)

        client.event.assert_not_awaited()
        callback.message.edit_text.assert_not_awaited()

    async def test_signing_up_keeps_one_message(
        self, locales: LocaleRepository, translator: Translator
    ) -> None:
        """Запись переписывает карточку и убирает кнопку, чтобы не записаться дважды."""
        await locales.set(1, "ru")
        callback = opened("join:4")
        client = api(None)
        client.register = AsyncMock(
            return_value=RegistrationResult(id=9, event_id=4, status="registered")
        )

        await join_event(callback, locales, translator, client)

        text = callback.message.edit_text.await_args.args[0]
        labels = [
            button.text
            for row in callback.message.edit_text.await_args.kwargs["reply_markup"].inline_keyboard
            for button in row
        ]
        assert "Вы записаны" in text
        assert "💛 Записаться" not in labels

    async def test_a_second_signup_is_explained(
        self, locales: LocaleRepository, translator: Translator
    ) -> None:
        """Повторная запись не пишет новое сообщение, а объясняет, что место уже есть."""
        callback = opened("join:4")
        client = api(None)
        client.register = AsyncMock(side_effect=ApiError(409, "conflict"))

        await join_event(callback, locales, translator, client)

        callback.answer.assert_awaited_once_with("Вы уже записаны на этот выезд.")
        callback.message.edit_text.assert_not_awaited()
