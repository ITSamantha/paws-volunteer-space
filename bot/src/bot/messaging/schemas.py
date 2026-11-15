from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict


class NotificationType(StrEnum):
    """Тип события; значения совпадают с теми, что публикует API."""

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


class NotificationMessage(BaseModel):
    """Событие от API: кому, о чём, насколько срочно и когда отправить.

    Приоритет: 1 — высокий, 2 — обычный, 3 — низкий. send_at=None значит «отправить сразу».
    """

    model_config = ConfigDict(frozen=True)

    id: str
    type: NotificationType
    priority: int
    telegram_id: int
    event_id: int | None = None
    payload: dict[str, Any] | None = None
    send_at: AwareDatetime | None = None
    key: str | None = None
    created_at: datetime
