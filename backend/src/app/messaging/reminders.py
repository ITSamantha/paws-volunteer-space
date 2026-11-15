from datetime import UTC, datetime, timedelta
from typing import ClassVar


class Reminders:
    """Когда напоминать о мероприятии."""

    BEFORE: ClassVar[timedelta] = timedelta(hours=24)

    @classmethod
    def send_at(cls, starts_at: datetime, now: datetime | None = None) -> datetime | None:
        """Время напоминания или None, если до начала осталось меньше положенного."""
        moment = starts_at - cls.BEFORE

        return moment if moment > (now or datetime.now(UTC)) else None

    @staticmethod
    def key(event_id: int) -> str:
        """Ключ замены: новое напоминание вытесняет прежнее, ещё не отправленное."""
        return f"reminder:{event_id}"
