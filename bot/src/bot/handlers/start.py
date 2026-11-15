from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.i18n.repository import LocaleRepository
from bot.i18n.translator import Translator

router = Router(name="start")


@router.message(CommandStart())
async def start(message: Message, locales: LocaleRepository, translator: Translator) -> None:
    """Приветствие; язык запоминается из настроек Telegram, если пользователь его не выбирал."""
    if message.from_user is None:
        return

    guessed = Translator.normalize(message.from_user.language_code)
    locale = await locales.set_if_absent(message.from_user.id, guessed)

    await message.answer(translator.translate(locale, "start-greeting"))
