from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, PgEnum
from app.database.mixins import TimestampMixin
from app.database.models.enums import EventStatus
from app.database.models.registration import Registration
from app.database.models.shelter import Shelter
from app.database.models.user import User


class Event(TimestampMixin, Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("capacity > 0", name="capacity_positive"),
        CheckConstraint("ends_at IS NULL OR ends_at > starts_at", name="ends_after_start"),
        Index("ix_events_status_starts_at", "status", "starts_at"),
        {"comment": "Волонтёрские мероприятия и поездки в приюты"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, comment="Внутренний идентификатор")
    title: Mapped[str] = mapped_column(String(255), comment="Название мероприятия")
    description: Mapped[str | None] = mapped_column(comment="Описание и формат активности")
    starts_at: Mapped[datetime] = mapped_column(comment="Дата и время начала")
    ends_at: Mapped[datetime | None] = mapped_column(comment="Дата и время окончания")
    shelter_id: Mapped[int | None] = mapped_column(
        ForeignKey("shelters.id", ondelete="SET NULL"),
        comment="Приют, в котором проходит мероприятие (если применимо)",
    )
    location: Mapped[str] = mapped_column(String(500), comment="Место встречи или адрес проведения")
    capacity: Mapped[int] = mapped_column(comment="Лимит участников; должен быть больше нуля")
    status: Mapped[EventStatus] = mapped_column(
        PgEnum.create(EventStatus, "event_status"),
        server_default=EventStatus.PLANNED.value,
        comment="Статус мероприятия",
    )
    instructions: Mapped[str | None] = mapped_column(
        comment="Что взять с собой, требования приюта, прочая инструкция"
    )
    comment: Mapped[str | None] = mapped_column(comment="Прочая информация о мероприятии")
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        comment="Организатор, создавший мероприятие",
    )

    shelter: Mapped[Shelter | None] = relationship(lazy="raise")
    creator: Mapped[User] = relationship(foreign_keys=[created_by], lazy="raise")
    registrations: Mapped[list[Registration]] = relationship(lazy="raise")
