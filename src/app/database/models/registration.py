from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, PgEnum
from app.database.mixins import CreatedAtMixin
from app.database.models.enums import RegistrationStatus
from app.database.models.user import User


class Registration(CreatedAtMixin, Base):
    __tablename__ = "registrations"
    __table_args__ = (
        CheckConstraint(
            "status <> 'cancelled' OR "
            "(cancellation_reason IS NOT NULL AND btrim(cancellation_reason) <> '')",
            name="cancelled_requires_reason",
        ),
        CheckConstraint(
            "(status = 'cancelled') = (cancelled_at IS NOT NULL)",
            name="cancelled_at_matches_status",
        ),
        CheckConstraint(
            "(decided_by IS NULL) = (decided_at IS NULL)",
            name="decision_author_matches_time",
        ),
        CheckConstraint(
            "status <> 'rejected' OR "
            "(decided_by IS NOT NULL AND decision_comment IS NOT NULL "
            "AND btrim(decision_comment) <> '')",
            name="rejected_requires_decision",
        ),
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
        comment="Дата и время отмены записи; заполнено тогда и только тогда, когда статус cancelled"
    )
    cancellation_reason: Mapped[str | None] = mapped_column(
        comment="Причина отмены записи; обязательна при статусе cancelled"
    )
    decided_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        comment="Ответственный организатор, принявший решение по заявке; NULL — решения не было",
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        comment="Дата и время решения; заполнено тогда и только тогда, когда есть decided_by"
    )
    decision_comment: Mapped[str | None] = mapped_column(
        comment="Комментарий к решению организатора; обязателен при статусе rejected"
    )

    user: Mapped[User] = relationship(foreign_keys=[user_id], lazy="raise")
