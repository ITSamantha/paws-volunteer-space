from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
)
from aiogram.methods import SendMessage

from bot.sending.errors import DeliveryError
from bot.sending.sender import TelegramSender

METHOD = SendMessage(chat_id=1, text="x")


def sender_with(error: Exception | None) -> tuple[TelegramSender, AsyncMock]:
    bot = MagicMock()
    bot.send_message = AsyncMock(side_effect=error)

    return TelegramSender(bot), bot.send_message


class TestTelegramSender:
    """Отправка через Telegram и разбор ошибок."""

    async def test_message_is_sent_to_the_chat(self) -> None:
        """Сообщение уходит в чат получателя."""
        sender, send_message = sender_with(None)

        await sender.send(42, "Привет")

        send_message.assert_awaited_once_with(chat_id=42, text="Привет")

    async def test_flood_limit_keeps_telegram_delay(self) -> None:
        """Лимит Telegram — временная ошибка, указанная задержка сохраняется."""
        sender, _ = sender_with(TelegramRetryAfter(METHOD, "Flood", 7))

        with pytest.raises(DeliveryError) as raised:
            await sender.send(1, "x")

        assert raised.value.retryable is True
        assert raised.value.retry_after == 7

    @pytest.mark.parametrize(
        "error",
        [
            TelegramForbiddenError(METHOD, "Forbidden: bot was blocked by the user"),
            TelegramBadRequest(METHOD, "Bad Request: chat not found"),
        ],
    )
    async def test_blocked_bot_and_missing_chat_are_permanent(self, error: Exception) -> None:
        """Заблокированный бот и несуществующий чат повторять бессмысленно."""
        sender, _ = sender_with(error)

        with pytest.raises(DeliveryError) as raised:
            await sender.send(1, "x")

        assert raised.value.retryable is False

    @pytest.mark.parametrize(
        "error", [TelegramNetworkError(METHOD, "сеть"), TelegramAPIError(METHOD, "сервер")]
    )
    async def test_network_and_server_errors_are_temporary(self, error: Exception) -> None:
        """Сетевые и серверные сбои можно повторить."""
        sender, _ = sender_with(error)

        with pytest.raises(DeliveryError) as raised:
            await sender.send(1, "x")

        assert raised.value.retryable is True
        assert raised.value.retry_after is None

    def test_bot_uses_html_parse_mode(self) -> None:
        """Бот отправляет сообщения с разметкой HTML."""
        bot = TelegramSender.create_bot("123456:test-token-0123456789")

        assert bot.default.parse_mode == "HTML"


class TestDeliveryError:
    """Ошибка доставки."""

    def test_defaults_to_retryable(self) -> None:
        """По умолчанию ошибку можно повторить, задержку выбирает очередь."""
        error = DeliveryError("сбой")

        assert error.retryable is True
        assert error.retry_after is None
        assert str(error) == "сбой"
