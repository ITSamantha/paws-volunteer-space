from typing import ClassVar

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from bot.handlers.language import LanguageChoice
from bot.i18n.repository import LocaleRepository
from bot.i18n.translator import Translator

router = Router(name="menu")


class Menu:
    """Кнопки главного меню. Разделы пока только показывают, что появятся дальше."""

    EVENTS: ClassVar[str] = "menu:events"
    MINE: ClassVar[str] = "menu:mine"
    ORGANIZER: ClassVar[str] = "menu:organizer"
    STAFF: ClassVar[frozenset[str]] = frozenset({"admin", "organizer", "smm"})

    @classmethod
    def keyboard(
        cls, translator: Translator, locale: str, roles: list[str]
    ) -> InlineKeyboardMarkup:
        """Кнопки волонтёра у всех. Организатору, администратору и SMM добавляется свой раздел."""
        translate = translator.translate
        rows = [
            [InlineKeyboardButton(text=translate(locale, "menu-events"), callback_data=cls.EVENTS)],
            [InlineKeyboardButton(text=translate(locale, "menu-mine"), callback_data=cls.MINE)],
        ]

        if cls.STAFF & set(roles):
            rows.append(
                [
                    InlineKeyboardButton(
                        text=translate(locale, "menu-organizer"), callback_data=cls.ORGANIZER
                    )
                ]
            )

        rows.extend(LanguageChoice.keyboard().inline_keyboard)

        return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data.in_({Menu.MINE, Menu.ORGANIZER}))
async def section_is_next(
    callback: CallbackQuery, locales: LocaleRepository, translator: Translator
) -> None:
    """Раздел ещё не собран: кнопка отвечает, что он следующий."""
    locale = await locales.get(callback.from_user.id) or Translator.normalize(None)

    await callback.answer(translator.translate(locale, "menu-soon"))
