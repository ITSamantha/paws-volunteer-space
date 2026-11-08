from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, PgEnum
from app.database.mixins import CreatedAtMixin
from app.database.models.enums import NotificationStatus, NotificationType


class Notification(CreatedAtMixin, Base):
    """Уведомление пользователю в очереди на отправку (outbox)."""

    __tablename__ = "notifications"
    __table_args__ = (
        Index(
            "ix_notifications_pending_scheduled_at",
            "scheduled_at",
            postgresql_where=text("status = 'pending'"),
        ),
        Index(
            "uq_notifications_user_id_dedup_key",
            "user_id",
            "dedup_key",
            unique=True,
            postgresql_where=text("dedup_key IS NOT NULL"),
        ),
        {"comment": "Очередь уведомлений пользователям (outbox)"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, comment="Внутренний идентификатор")
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, comment="Получатель"
    )
    type: Mapped[NotificationType] = mapped_column(
        PgEnum.create(NotificationType, "notification_type"), comment="Тип уведомления"
    )
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"),
        comment="Мероприятие, о котором уведомление",
    )
    broadcast_id: Mapped[int | None] = mapped_column(
        ForeignKey("broadcasts.id", ondelete="CASCADE"),
        index=True,
        comment="Рассылка, из которой создано уведомление",
    )
    payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, comment="Данные для подстановки в шаблон сообщения"
    )
    dedup_key: Mapped[str | None] = mapped_column(
        String(255),
        comment="Ключ защиты от дублей: у получателя не бывает двух уведомлений с одним ключом",
    )
    status: Mapped[NotificationStatus] = mapped_column(
        PgEnum.create(NotificationStatus, "notification_status"),
        server_default=NotificationStatus.PENDING.value,
        comment="Статус отправки",
    )
    scheduled_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        comment="Дата и время, раньше которых не отправлять (для напоминаний)",
    )
    sent_at: Mapped[datetime | None] = mapped_column(comment="Дата и время фактической отправки")
    attempts: Mapped[int] = mapped_column(
        server_default=text("0"), comment="Сколько попыток отправки уже было"
    )
    last_error: Mapped[str | None] = mapped_column(comment="Текст последней ошибки отправки")
