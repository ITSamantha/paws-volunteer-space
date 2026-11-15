import pytest

from app.database.models.enums import NotificationPriority, NotificationType


class TestNotificationPriority:
    """Приоритет уведомления определяется его типом."""

    @pytest.mark.parametrize(
        "notification_type",
        [
            NotificationType.EVENT_CANCELLED,
            NotificationType.EVENT_CHANGED,
            NotificationType.SPOT_FREED,
        ],
    )
    def test_urgent_types_go_first(self, notification_type: NotificationType) -> None:
        """Отмена, изменение мероприятия и освободившееся место отправляются в первую очередь."""
        assert notification_type.priority is NotificationPriority.HIGH

    @pytest.mark.parametrize(
        "notification_type", [NotificationType.NEW_EVENT, NotificationType.BROADCAST]
    )
    def test_mass_messages_go_last(self, notification_type: NotificationType) -> None:
        """Анонсы и рассылки не задерживают остальные уведомления."""
        assert notification_type.priority is NotificationPriority.LOW

    @pytest.mark.parametrize(
        "notification_type",
        [
            NotificationType.REGISTRATION_CONFIRMED,
            NotificationType.REGISTRATION_PENDING,
            NotificationType.REGISTRATION_APPROVED,
            NotificationType.REGISTRATION_REJECTED,
            NotificationType.REGISTRATION_WAITLISTED,
            NotificationType.REGISTRATION_CANCELLED,
            NotificationType.REMINDER,
            NotificationType.ORGANIZER_NEW_REGISTRATION,
            NotificationType.ORGANIZER_APPROVAL_REQUESTED,
            NotificationType.ORGANIZER_CANCELLATION,
            NotificationType.USER_BLOCKED,
        ],
    )
    def test_the_rest_is_normal(self, notification_type: NotificationType) -> None:
        """Ответы на действия пользователя и сообщения организаторам идут с обычным приоритетом."""
        assert notification_type.priority is NotificationPriority.NORMAL

    def test_every_type_has_a_priority_the_database_accepts(self) -> None:
        """У каждого типа приоритет попадает в диапазон, который принимает БД."""
        assert all(1 <= item.priority <= 3 for item in NotificationType)
