from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, PgEnum
from app.database.mixins import CreatedAtMixin
from app.database.models.enums import BroadcastAudience, BroadcastStatus
from app.database.models.user import User


class Broadcast(CreatedAtMixin, Base):
    __tablename__ = "broadcasts"
    __table_args__ = (
        CheckConstraint(
            "(audience = 'event_participants') = (event_id IS NOT NULL)",
            name="event_matches_audience",
        ),
        {"comment": "Рассылки"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, comment="Внутренний идентификатор")
    author_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, comment="Автор рассылки"
    )
    text: Mapped[str] = mapped_column(comment="Текст рассылки")
    audience: Mapped[BroadcastAudience] = mapped_column(
        PgEnum.create(BroadcastAudience, "broadcast_audience"),
        comment="Аудитория рассылки",
    )
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("events.id", ondelete="RESTRICT"),
        comment="Мероприятие, участникам которого адресована рассылка",
    )
    status: Mapped[BroadcastStatus] = mapped_column(
        PgEnum.create(BroadcastStatus, "broadcast_status"),
        server_default=BroadcastStatus.DRAFT.value,
        comment="Статус рассылки",
    )
    sent_at: Mapped[datetime | None] = mapped_column(comment="Дата и время отправки рассылки")

    author: Mapped[User] = relationship(lazy="raise")
