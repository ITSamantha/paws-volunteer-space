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

    try:
        items = await api.own_registrations(callback.from_user.id)
    except ApiError:
        text = translate(locale, "events-unavailable")
    else:
        text = __text(translator, locale, items)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=translate(locale, "menu-back"), callback_data="menu:back")]
        ]
    )

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
