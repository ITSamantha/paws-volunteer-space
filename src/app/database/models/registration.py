from datetime import datetime

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, PgEnum
from app.database.mixins import CreatedAtMixin
from app.database.models.enums import RegistrationStatus
from app.database.models.user import User


class Registration(CreatedAtMixin, Base):
    __tablename__ = "registrations"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_registrations_event_id_user_id"),
        Index("ix_registrations_event_id_status", "event_id", "status"),
        {"comment": "Записи волонтёров на мероприятия"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, comment="Внутренний идентификатор")
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="RESTRICT"), comment="Мероприятие"
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, comment="Волонтёр"
    )
    status: Mapped[RegistrationStatus] = mapped_column(
        PgEnum.create(RegistrationStatus, "registration_status"),
        server_default=RegistrationStatus.REGISTERED.value,
        comment="Статус записи",
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        comment="Дата и время отмены записи; NULL, если не отменялась"
    )

    user: Mapped[User] = relationship(lazy="raise")
