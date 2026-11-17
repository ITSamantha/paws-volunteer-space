from typing import ClassVar

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.api.client import ApiClient
from bot.handlers.screen import Screen
from bot.i18n.repository import LocaleRepository
from bot.i18n.translator import Translator

router = Router(name="language")


class LanguageChoice:
    """Выбор языка кнопками: клавиатуру можно вставить в любое меню."""

    PREFIX: ClassVar[str] = "language:"
    NAMES: ClassVar[dict[str, str]] = {"ru": "Русский", "en": "English"}

    @classmethod
    def keyboard(cls) -> InlineKeyboardMarkup:
        """Кнопки с названиями языков, каждое название — на своём языке."""
        buttons = [
            InlineKeyboardButton(text=name, callback_data=cls.PREFIX + code)
            for code, name in cls.NAMES.items()
        ]

        return InlineKeyboardMarkup(inline_keyboard=[buttons])


@router.callback_query(F.data.startswith(LanguageChoice.PREFIX))
async def set_language(
    callback: CallbackQuery, locales: LocaleRepository, translator: Translator, api: ApiClient
) -> None:
    """Сохраняет язык и переписывает то же меню на нём, не добавляя сообщение."""
    locale = Translator.normalize((callback.data or "").removeprefix(LanguageChoice.PREFIX))

    await locales.set(callback.from_user.id, locale)

    from bot.handlers.menu import Menu
    from bot.handlers.start import roles_of

    roles = await roles_of(api, callback.from_user.id)

    if isinstance(callback.message, Message):
        await Screen.replace(
            callback.message,
            translator.translate(locale, "start-greeting"),
            Menu.keyboard(translator, locale, roles),
        )

    await callback.answer()
