from sqlalchemy import CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.mixins import CreatedAtMixin, SoftDeleteMixin


class Bonus(CreatedAtMixin, SoftDeleteMixin, Base):
    __tablename__ = "bonuses"
    __table_args__ = (
        CheckConstraint("title = btrim(title) AND title <> ''", name="title_trimmed"),
        Index(
            "uq_bonuses_title_lower",
            text("lower(title)"),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        {"comment": "Справочник бонусов за участие в мероприятиях"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, comment="Внутренний идентификатор")
    title: Mapped[str] = mapped_column(String(255), comment="Название бонуса")
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        comment="Кто добавил бонус; NULL — бонус из начального справочника",
    )


class EventBonus(Base):
    __tablename__ = "event_bonuses"
    __table_args__ = {"comment": "Бонусы, которые получают участники мероприятия"}

    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), primary_key=True, comment="Мероприятие"
    )
    bonus_id: Mapped[int] = mapped_column(
        ForeignKey("bonuses.id", ondelete="RESTRICT"),
        primary_key=True,
        index=True,
        comment="Бонус",
    )
