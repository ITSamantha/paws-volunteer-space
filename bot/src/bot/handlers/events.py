from typing import ClassVar

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.api.client import ApiClient, ApiError, EventCard, EventLine, RegistrationResult
from bot.handlers.menu import Menu
from bot.handlers.screen import Screen
from bot.handlers.start import roles_of
from bot.i18n.repository import LocaleRepository
from bot.i18n.translator import Translator

router = Router(name="events")


class EventList:
    """Список выездов внутри того же сообщения меню."""

    OPEN: ClassVar[str] = "event:"
    JOIN: ClassVar[str] = "join:"
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

    @classmethod
    def card_keyboard(
        cls, event_id: int, join: str | None, to_list: str, back: str
    ) -> InlineKeyboardMarkup:
        """Запись, возврат к списку и в главное меню."""
        rows = []

        if join is not None:
            rows.append(
                [InlineKeyboardButton(text=join, callback_data=cls.JOIN + str(event_id))]
            )

        rows.append([InlineKeyboardButton(text=to_list, callback_data=Menu.EVENTS)])
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
async def show_event(
    callback: CallbackQuery, locales: LocaleRepository, translator: Translator, api: ApiClient
) -> None:
    """Открывает карточку выезда в том же сообщении."""
    if not isinstance(callback.message, Message):
        await callback.answer()

        return

    locale = await locales.get(callback.from_user.id) or Translator.normalize(None)
    event_id = __event_id(callback.data or "")

    if event_id is None:
        await callback.answer()

        return

    try:
        card = await api.event(callback.from_user.id, event_id)
    except ApiError:
        await Screen.replace(
            callback.message,
            translator.translate(locale, "events-unavailable"),
            EventList.keyboard([], translator.translate(locale, "menu-back")),
        )
        await callback.answer()

        return

    text = __card_text(translator, locale, card)
    keyboard = EventList.card_keyboard(
        card.id,
        translator.translate(locale, "events-join"),
        translator.translate(locale, "events-to-list"),
        translator.translate(locale, "menu-back"),
    )

    await Screen.replace(callback.message, text, keyboard)
    await callback.answer()


def __event_id(data: str) -> int | None:
    """Достаёт ID выезда из callback; пустое или чужое значение не подходит."""
    raw = data.removeprefix(EventList.OPEN)

    if not raw.isdigit():
        return None

    event_id = int(raw)

    return event_id


def __card_text(translator: Translator, locale: str, card: EventCard) -> str:
    """Текст карточки: когда, куда и сколько мест свободно."""
    place = card.location

    if place is None and card.shelter is not None:
        place = card.shelter.address or card.shelter.title

    free = max(card.capacity - card.occupied, 0)
    text = translator.translate(
        locale,
        "events-card",
        title=card.title,
        when=translator.moment(locale, card.starts_at),
        place=place or translator.translate(locale, "events-place-unknown"),
        free=free,
        capacity=card.capacity,
        details=card.instructions or card.description or "",
    )

    return text


@router.callback_query(F.data.startswith(EventList.JOIN))
async def join_event(
    callback: CallbackQuery, locales: LocaleRepository, translator: Translator, api: ApiClient
) -> None:
    """Записывает на выезд и оставляет результат в том же сообщении."""
    if not isinstance(callback.message, Message):
        await callback.answer()

        return

    locale = await locales.get(callback.from_user.id) or Translator.normalize(None)
    event_id = __event_id((callback.data or "").replace(EventList.JOIN, EventList.OPEN, 1))

    if event_id is None:
        await callback.answer()

        return

    try:
        result = await api.register(callback.from_user.id, event_id)
    except ApiError as error:
        key = "events-already" if error.status_code == 409 else "events-unavailable"
        await callback.answer(translator.translate(locale, key))

        return

    text = __joined_text(translator, locale, result)
    keyboard = EventList.card_keyboard(
        event_id,
        None,
        translator.translate(locale, "events-to-list"),
        translator.translate(locale, "menu-back"),
    )

    await Screen.replace(callback.message, text, keyboard)
    await callback.answer()


def __joined_text(translator: Translator, locale: str, result: RegistrationResult) -> str:
    """Понятный итог записи по статусу, который вернул API."""
    known = {"registered", "pending", "waitlisted"}
    key = "events-joined-" + result.status if result.status in known else "events-unavailable"
    text = translator.translate(locale, key)

    return text


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
