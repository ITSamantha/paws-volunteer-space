from enum import IntEnum, StrEnum


class UserStatus(StrEnum):
    """Статус пользователя."""

    ACTIVE = "active"
    BLOCKED = "blocked"


class RoleType(StrEnum):
    """Дополнительная роль пользователя; без роли пользователь — волонтёр."""

    ORGANIZER = "organizer"
    SMM = "smm"
    ADMIN = "admin"


class ContactType(StrEnum):
    """Тип контакта приюта."""

    PHONE = "phone"
    EMAIL = "email"
    WEBSITE = "website"
    VK = "vk"
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    OTHER = "other"


class EventStatus(StrEnum):
    """Статус мероприятия."""

    PLANNED = "planned"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class RegistrationStatus(StrEnum):
    """Статус записи на мероприятие."""

    REGISTERED = "registered"
    PENDING = "pending"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    WAITLISTED = "waitlisted"
    ATTENDED = "attended"
    ABSENT = "absent"


class BroadcastAudience(StrEnum):
    """Аудитория рассылки."""

    ALL = "all"
    ANNOUNCEMENTS_SUBSCRIBERS = "announcements_subscribers"
    EVENT_PARTICIPANTS = "event_participants"


class BroadcastStatus(StrEnum):
    """Статус рассылки."""

    DRAFT = "draft"
    QUEUED = "queued"
    SENT = "sent"


class NotificationPriority(IntEnum):
    """Приоритет отправки уведомления: чем меньше число, тем раньше уходит."""

    HIGH = 1
    NORMAL = 2
    LOW = 3


class NotificationType(StrEnum):
    """Тип уведомления."""

    REGISTRATION_CONFIRMED = "registration_confirmed"
    REGISTRATION_PENDING = "registration_pending"
    REGISTRATION_APPROVED = "registration_approved"
    REGISTRATION_REJECTED = "registration_rejected"
    REGISTRATION_WAITLISTED = "registration_waitlisted"
    SPOT_FREED = "spot_freed"
    REGISTRATION_CANCELLED = "registration_cancelled"
    EVENT_CHANGED = "event_changed"
    EVENT_CANCELLED = "event_cancelled"
    REMINDER = "reminder"
    NEW_EVENT = "new_event"
    ORGANIZER_NEW_REGISTRATION = "organizer_new_registration"
    ORGANIZER_APPROVAL_REQUESTED = "organizer_approval_requested"
    ORGANIZER_CANCELLATION = "organizer_cancellation"
    USER_BLOCKED = "user_blocked"
    BROADCAST = "broadcast"

    @property
    def priority(self) -> NotificationPriority:
        """Приоритет по типу: срочное — вперёд, массовые рассылки — в конец очереди."""
        match self:
            case (
                NotificationType.EVENT_CANCELLED
                | NotificationType.EVENT_CHANGED
                | NotificationType.SPOT_FREED
            ):
                return NotificationPriority.HIGH
            case NotificationType.NEW_EVENT | NotificationType.BROADCAST:
                return NotificationPriority.LOW
            case _:
                return NotificationPriority.NORMAL
