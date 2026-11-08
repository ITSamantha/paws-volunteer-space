from enum import StrEnum


class UserStatus(StrEnum):
    ACTIVE = "active"
    BLOCKED = "blocked"


class RoleType(StrEnum):
    ORGANIZER = "organizer"
    SMM = "smm"
    ADMIN = "admin"


class ContactType(StrEnum):
    PHONE = "phone"
    EMAIL = "email"
    WEBSITE = "website"
    VK = "vk"
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    OTHER = "other"


class EventStatus(StrEnum):
    PLANNED = "planned"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class RegistrationStatus(StrEnum):
    REGISTERED = "registered"
    PENDING = "pending"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    WAITLISTED = "waitlisted"
    ATTENDED = "attended"
    ABSENT = "absent"


class BroadcastAudience(StrEnum):
    ALL = "all"
    ANNOUNCEMENTS_SUBSCRIBERS = "announcements_subscribers"
    EVENT_PARTICIPANTS = "event_participants"


class BroadcastStatus(StrEnum):
    DRAFT = "draft"
    QUEUED = "queued"
    SENT = "sent"


class NotificationType(StrEnum):
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
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
