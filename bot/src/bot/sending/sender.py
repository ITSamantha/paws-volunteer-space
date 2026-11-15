from typing import Protocol

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)

from bot.sending.errors import DeliveryError


class Sender(Protocol):
    """Отправитель сообщений пользователям."""

    async def send(self, telegram_id: int, text: str) -> None:
        """Отправляет сообщение; при неудаче выбрасывает DeliveryError."""


class TelegramSender:
    """Отправка через Telegram Bot API; ошибки превращаются в DeliveryError."""

    def __init__(self, bot: Bot) -> None:
        """Работает через переданного бота."""
        self.__bot = bot

    @staticmethod
    def create_bot(token: str) -> Bot:
        """Бот с разметкой HTML по умолчанию."""
        return Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    async def send(self, telegram_id: int, text: str) -> None:
        """Отправляет сообщение; при неудаче выбрасывает DeliveryError."""
        try:
            await self.__bot.send_message(chat_id=telegram_id, text=text)
        except TelegramRetryAfter as error:
            raise DeliveryError(
                str(error), retryable=True, retry_after=error.retry_after
            ) from error
        except (TelegramForbiddenError, TelegramBadRequest) as error:
            raise DeliveryError(str(error), retryable=False) from error
        except TelegramAPIError as error:
            raise DeliveryError(str(error), retryable=True) from error
