from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.api.client import ApiClient, ApiError
from bot.handlers.menu import Menu
from bot.handlers.screen import Screen
from bot.i18n.repository import LocaleRepository
from bot.i18n.translator import Translator

router = Router(name="start")


@router.message(CommandStart())
async def start(
    message: Message, locales: LocaleRepository, translator: Translator, api: ApiClient
) -> None:
    """Приветствие и меню. Язык берётся из Telegram, если пользователь его не выбирал."""
    if message.from_user is None:
        return

    guessed = Translator.normalize(message.from_user.language_code)
    locale = await locales.set_if_absent(message.from_user.id, guessed)
    roles = await roles_of(api, message.from_user.id)
    keyboard = Menu.keyboard(translator, locale, roles)

    await Screen.show(
        message,
        locales,
        message.from_user.id,
        translator.translate(locale, "start-greeting"),
        keyboard,
    )


async def roles_of(api: ApiClient, telegram_id: int) -> list[str]:
    """Роли пользователя. Если API недоступен или человек не зарегистрирован, меню волонтёра."""
    try:
        profile = await api.profile(telegram_id)
    except ApiError:
        return []

    if profile is None:
        return []

    return profile.roles
