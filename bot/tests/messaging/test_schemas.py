import json

import pytest
from pydantic import ValidationError

from bot.messaging.schemas import NotificationMessage, NotificationType


class TestNotificationMessage:
    """Контракт с API: так сообщение приходит из Kafka."""

    BACKEND_SAMPLE = json.dumps(
        {
            "id": "3f2a9c7e1b5d4c0e8a6b2d1f0e9c8b7a",
            "type": "reminder",
            "priority": 2,
            "telegram_id": 4242,
            "event_id": 7,
            "payload": {"title": "Выезд", "starts_at": "2030-01-02T10:00:00+00:00"},
            "send_at": "2030-01-01T10:00:00Z",
            "key": "reminder:7",
            "created_at": "2030-01-01T09:00:00Z",
        }
    )

    def test_parses_what_the_backend_publishes(self) -> None:
        """Сообщение, как его публикует API, читается без ошибок."""
        message = NotificationMessage.model_validate_json(self.BACKEND_SAMPLE)

        assert message.type is NotificationType.REMINDER
        assert message.telegram_id == 4242
        assert message.send_at is not None
        assert message.send_at.tzinfo is not None
        assert message.key == "reminder:7"

    def test_optional_fields_may_be_missing(self) -> None:
        """Время отправки, ключ, мероприятие и данные необязательны."""
        message = NotificationMessage.model_validate(
            {
                "id": "x",
                "type": "broadcast",
                "priority": 3,
                "telegram_id": 1,
                "created_at": "2030-01-01T09:00:00Z",
            }
        )

        assert message.send_at is None
        assert message.key is None
        assert message.event_id is None
        assert message.payload is None

    def test_unknown_type_is_rejected(self) -> None:
        """Неизвестный тип события отклоняется."""
        with pytest.raises(ValidationError):
            NotificationMessage.model_validate_json(
                self.BACKEND_SAMPLE.replace('"reminder"', '"unknown"')
            )

    def test_send_time_without_zone_is_rejected(self) -> None:
        """Время отправки без часового пояса отклоняется: момент должен быть однозначным."""
        with pytest.raises(ValidationError):
            NotificationMessage.model_validate_json(
                self.BACKEND_SAMPLE.replace("2030-01-01T10:00:00Z", "2030-01-01T10:00:00")
            )
