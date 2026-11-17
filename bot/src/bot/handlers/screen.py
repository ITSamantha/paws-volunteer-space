from collections.abc import Awaitable

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, Message

from bot.i18n.repository import LocaleRepository


class Screen:
    """Одно сообщение меню в личке. Уведомления этим классом не отправляются и не удаляются."""

    @staticmethod
    async def show(
        message: Message,
        locales: LocaleRepository,
        telegram_id: int,
        text: str,
        keyboard: InlineKeyboardMarkup,
    ) -> None:
        """Удаляет прошлое меню и команду, которая его открыла, и оставляет одно новое сообщение."""
        previous = await locales.menu_message_id(telegram_id)

        if previous is not None and message.bot is not None:
            await Screen.__remove(message.bot.delete_message(message.chat.id, previous))

        sent = await message.answer(text, reply_markup=keyboard)

        await locales.remember_menu(telegram_id, sent.message_id)
        await Screen.__remove(message.delete())

    @staticmethod
    async def replace(message: Message, text: str, keyboard: InlineKeyboardMarkup) -> None:
        """Меняет текст и кнопки того же сообщения, не добавляя новое."""
        await message.edit_text(text, reply_markup=keyboard)

    @staticmethod
    async def __remove(deletion: Awaitable[object]) -> None:
        """Удаление не должно ломать ответ, если сообщение уже исчезло."""
        try:
            await deletion
        except TelegramBadRequest:
            return
