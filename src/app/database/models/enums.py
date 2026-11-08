from enum import StrEnum


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


class NotificationStatus(StrEnum):
    """Статус отправки уведомления."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
