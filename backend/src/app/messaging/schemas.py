from typing import Any
from uuid import uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.database.models.enums import NotificationType


class NotificationMessage(BaseModel):
    """Событие для бота: кому, о чём, насколько срочно и когда отправить.

    Бэкенд только публикует его. Очередь, соблюдение времени (send_at), порядок по приоритету,
    повторные попытки и отправка в Telegram целиком на стороне бота. Бот отбрасывает повторы
    по id, а сообщение с тем же (telegram_id, key) заменяет ещё не отправленное прежнее.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: uuid4().hex)
    type: NotificationType
    priority: int
    telegram_id: int
    event_id: int | None = None
    payload: dict[str, Any] | None = None
    send_at: AwareDatetime | None = None
    key: str | None = None
    created_at: AwareDatetime
