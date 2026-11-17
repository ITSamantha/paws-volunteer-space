from typing import ClassVar

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.api.client import ApiClient, ApiError, EventLine
from bot.handlers.menu import Menu
from bot.handlers.screen import Screen
from bot.handlers.start import roles_of
from bot.i18n.repository import LocaleRepository
from bot.i18n.translator import Translator

router = Router(name="events")


class EventList:
    """Список выездов внутри того же сообщения меню."""

    OPEN: ClassVar[str] = "event:"
    BACK: ClassVar[str] = "menu:back"

    @classmethod
    def keyboard(cls, events: list[EventLine], back: str) -> InlineKeyboardMarkup:
        """Кнопка на каждый выезд и возврат в меню."""
        rows = [
            [InlineKeyboardButton(text=cls.__label(event), callback_data=cls.OPEN + str(event.id))]
            for event in events
        ]
        rows.append([InlineKeyboardButton(text=back, callback_data=cls.BACK)])
        keyboard = InlineKeyboardMarkup(inline_keyboard=rows)

        return keyboard

    @staticmethod
    def __label(event: EventLine) -> str:
        """Короткая подпись: название и сколько мест ещё свободно."""
        free = max(event.capacity - event.occupied, 0)
        title = event.title if len(event.title) <= 28 else event.title[:27] + "…"
        label = f"🐾 {title} · {free}"

        return label


@router.callback_query(F.data == Menu.EVENTS)
async def show_events(
    callback: CallbackQuery, locales: LocaleRepository, translator: Translator, api: ApiClient
) -> None:
    """Открывает список выездов в том же сообщении."""
    if not isinstance(callback.message, Message):
        await callback.answer()

        return

    locale = await locales.get(callback.from_user.id) or Translator.normalize(None)
    translate = translator.translate

    try:
        page = await api.events(callback.from_user.id)
    except ApiError:
        await Screen.replace(
            callback.message,
            translate(locale, "events-unavailable"),
            EventList.keyboard([], translate(locale, "menu-back")),
        )
        await callback.answer()

        return

    text = translate(locale, "events-title") if page.items else translate(locale, "events-empty")
    keyboard = EventList.keyboard(page.items, translate(locale, "menu-back"))

    await Screen.replace(callback.message, text, keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith(EventList.OPEN))
async def event_card_is_next(
    callback: CallbackQuery, locales: LocaleRepository, translator: Translator
) -> None:
    """Карточка выезда ещё не собрана."""
    locale = await locales.get(callback.from_user.id) or Translator.normalize(None)
    text = translator.translate(locale, "events-card-soon")

    await callback.answer(text)


@router.callback_query(F.data == EventList.BACK)
async def back_to_menu(
    callback: CallbackQuery, locales: LocaleRepository, translator: Translator, api: ApiClient
) -> None:
    """Возвращает приветствие и главное меню в то же сообщение."""
    if not isinstance(callback.message, Message):
        await callback.answer()

        return

    locale = await locales.get(callback.from_user.id) or Translator.normalize(None)
    roles = await roles_of(api, callback.from_user.id)
    keyboard = Menu.keyboard(translator, locale, roles)

    await Screen.replace(callback.message, translator.translate(locale, "start-greeting"), keyboard)
    await callback.answer()
