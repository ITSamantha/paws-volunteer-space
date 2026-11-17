from typing import ClassVar

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.api.client import ApiClient, ApiError, OwnRegistration
from bot.handlers.menu import Menu
from bot.handlers.screen import Screen
from bot.i18n.repository import LocaleRepository
from bot.i18n.translator import Translator

router = Router(name="mine")

STATUSES = (
    "registered",
    "pending",
    "waitlisted",
    "rejected",
    "cancelled",
    "attended",
    "absent",
)
CANCELLABLE = {"registered", "pending", "waitlisted"}


class Mine:
    """Отмена своей записи внутри того же сообщения."""

    CANCEL: ClassVar[str] = "cancel:"
    REASON: ClassVar[str] = "reason:"
    CODES: ClassVar[tuple[str, ...]] = ("plans", "busy", "sick")


@router.callback_query(F.data == Menu.MINE)
async def show_mine(
    callback: CallbackQuery, locales: LocaleRepository, translator: Translator, api: ApiClient
) -> None:
    """Показывает свои записи в том же сообщении."""
    if not isinstance(callback.message, Message):
        await callback.answer()

        return

    locale = await locales.get(callback.from_user.id) or Translator.normalize(None)
    translate = translator.translate

    items: list[OwnRegistration] = []

    try:
        items = await api.own_registrations(callback.from_user.id)
    except ApiError:
        text = translate(locale, "events-unavailable")
    else:
        text = __text(translator, locale, items)

    keyboard = __keyboard(translator, locale, items)

    await Screen.replace(callback.message, text, keyboard)
    await callback.answer()


def __text(translator: Translator, locale: str, items: list[OwnRegistration]) -> str:
    """Список своих выездов или честная пустая фраза."""
    if not items:
        text = translator.translate(locale, "mine-empty")

        return text

    lines = [translator.translate(locale, "mine-title")]

    for item in items:
        status = item.status if item.status in STATUSES else "registered"
        lines.append(
            translator.translate(
                locale,
                "mine-line",
                title=item.event.title,
                when=translator.moment(locale, item.event.starts_at),
                status=translator.translate(locale, "status-" + status),
            )
        )

    text = "\n".join(lines)

    return text


def __keyboard(
    translator: Translator, locale: str, items: list[OwnRegistration]
) -> InlineKeyboardMarkup:
    """Кнопка отмены у активных записей и возврат в меню."""
    rows = [
        [
            InlineKeyboardButton(
                text=translator.translate(locale, "mine-cancel", title=__short(item.event.title)),
                callback_data=Mine.CANCEL + str(item.event.id),
            )
        ]
        for item in items
        if item.status in CANCELLABLE
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text=translator.translate(locale, "menu-back"), callback_data="menu:back"
            )
        ]
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=rows)

    return keyboard


def __short(title: str) -> str:
    """Короткая подпись кнопки."""
    label = title if len(title) <= 24 else title[:23] + "…"

    return label


@router.callback_query(F.data.startswith(Mine.CANCEL))
async def ask_reason(
    callback: CallbackQuery, locales: LocaleRepository, translator: Translator
) -> None:
    """Спрашивает причину готовыми кнопками, не прося печатать текст."""
    if not isinstance(callback.message, Message):
        await callback.answer()

        return

    locale = await locales.get(callback.from_user.id) or Translator.normalize(None)
    event_id = __event_id(callback.data or "", Mine.CANCEL)

    if event_id is None:
        await callback.answer()

        return

    translate = translator.translate
    rows = [
        [
            InlineKeyboardButton(
                text=translate(locale, "reason-" + code),
                callback_data=f"{Mine.REASON}{event_id}:{code}",
            )
        ]
        for code in Mine.CODES
    ]
    rows.append(
        [InlineKeyboardButton(text=translate(locale, "menu-back"), callback_data=Menu.MINE)]
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=rows)

    await Screen.replace(callback.message, translate(locale, "cancel-ask"), keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith(Mine.REASON))
async def confirm_cancel(
    callback: CallbackQuery, locales: LocaleRepository, translator: Translator, api: ApiClient
) -> None:
    """Отменяет запись с выбранной причиной и оставляет итог в том же сообщении."""
    if not isinstance(callback.message, Message):
        await callback.answer()

        return

    locale = await locales.get(callback.from_user.id) or Translator.normalize(None)
    parsed = __reason(callback.data or "")

    if parsed is None:
        await callback.answer()

        return

    event_id, code = parsed

    try:
        await api.cancel(
            callback.from_user.id, event_id, translator.translate(locale, "reason-" + code)
        )
    except ApiError:
        await callback.answer(translator.translate(locale, "events-unavailable"))

        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=translator.translate(locale, "menu-back"), callback_data=Menu.MINE
                )
            ]
        ]
    )

    await Screen.replace(callback.message, translator.translate(locale, "cancel-done"), keyboard)
    await callback.answer()


def __event_id(data: str, prefix: str) -> int | None:
    """Достаёт ID мероприятия из callback."""
    raw = data.removeprefix(prefix).split(":", maxsplit=1)[0]

    if not raw.isdigit():
        return None

    event_id = int(raw)

    return event_id


def __reason(data: str) -> tuple[int, str] | None:
    """Пара ID и код причины. Чужой код не принимается."""
    event_id = __event_id(data, Mine.REASON)
    code = data.rsplit(":", maxsplit=1)[-1]

    if event_id is None or code not in Mine.CODES:
        return None

    parsed = (event_id, code)

    return parsed
