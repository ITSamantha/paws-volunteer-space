from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from app.database.models.enums import NotificationType
from app.messaging.schemas import NotificationMessage


def message(**fields: Any) -> NotificationMessage:
    values: dict[str, Any] = {
        "type": NotificationType.SPOT_FREED,
        "priority": 1,
        "telegram_id": 100,
        "event_id": 5,
        "payload": {"title": "Выезд"},
        "created_at": datetime(2030, 1, 1, 9, tzinfo=UTC),
    }

    return NotificationMessage.model_validate({**values, **fields})


class TestNotificationMessage:
    """Формат события, которое получает бот."""

    def test_round_trips_through_json(self) -> None:
        """Сообщение без потерь превращается в JSON и обратно."""
        original = message(send_at=datetime(2030, 1, 2, 10, tzinfo=UTC), key="reminder:5")

        restored = NotificationMessage.model_validate_json(original.model_dump_json())

        assert restored == original

    def test_json_has_plain_values(self) -> None:
        """В JSON тип — строка, время — ISO 8601: бот не зависит от Python-классов."""
        data = message(send_at=datetime(2030, 1, 2, 10, tzinfo=UTC)).model_dump(mode="json")

        assert data["type"] == "spot_freed"
        assert data["send_at"] == "2030-01-02T10:00:00Z"

    def test_send_at_is_empty_by_default(self) -> None:
        """Без времени отправки сообщение уходит сразу."""
        assert message().send_at is None
        assert message().key is None

    def test_every_message_gets_its_own_id(self) -> None:
        """Идентификатор уникален: по нему бот отбрасывает повторы."""
        assert message().id != message().id

    @pytest.mark.parametrize("field", ["send_at", "created_at"])
    def test_time_without_zone_is_rejected(self, field: str) -> None:
        """Время без часового пояса отклоняется."""
        with pytest.raises(ValidationError):
            message(**{field: datetime(2030, 1, 1, 10)})

    def test_unknown_type_is_rejected(self) -> None:
        """Неизвестный тип уведомления отклоняется."""
        with pytest.raises(ValidationError):
            message(type="unknown")
