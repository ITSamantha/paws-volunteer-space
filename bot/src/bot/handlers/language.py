from typing import ClassVar

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

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
    callback: CallbackQuery, locales: LocaleRepository, translator: Translator
) -> None:
    """Сохраняет выбранный язык и подтверждает его на этом же языке."""
    locale = Translator.normalize((callback.data or "").removeprefix(LanguageChoice.PREFIX))

    await locales.set(callback.from_user.id, locale)

    if isinstance(callback.message, Message):
        await callback.message.answer(translator.translate(locale, "language-changed"))

    await callback.answer()
