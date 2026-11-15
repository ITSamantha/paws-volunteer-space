from datetime import UTC, datetime, timedelta

from app.messaging.reminders import Reminders


class TestReminders:
    """Когда напоминать о мероприятии."""

    def test_reminder_is_a_day_before(self) -> None:
        """Напоминание назначается за сутки до начала."""
        now = datetime(2030, 1, 1, tzinfo=UTC)
        starts_at = now + timedelta(days=3)

        assert Reminders.send_at(starts_at, now) == starts_at - timedelta(hours=24)

    def test_no_reminder_when_too_late(self) -> None:
        """Если до начала меньше суток, напоминания нет."""
        now = datetime(2030, 1, 1, tzinfo=UTC)

        assert Reminders.send_at(now + timedelta(hours=5), now) is None

    def test_no_reminder_exactly_at_the_boundary(self) -> None:
        """Ровно за сутки момент уже наступил, напоминание не назначается."""
        now = datetime(2030, 1, 1, tzinfo=UTC)

        assert Reminders.send_at(now + timedelta(hours=24), now) is None

    def test_uses_current_time_by_default(self) -> None:
        """Без явного «сейчас» берётся текущее время."""
        assert Reminders.send_at(datetime.now(UTC) + timedelta(days=3)) is not None
        assert Reminders.send_at(datetime.now(UTC) + timedelta(hours=1)) is None

    def test_key_is_per_event(self) -> None:
        """Ключ замены зависит от мероприятия."""
        assert Reminders.key(5) == "reminder:5"
        assert Reminders.key(5) != Reminders.key(6)
