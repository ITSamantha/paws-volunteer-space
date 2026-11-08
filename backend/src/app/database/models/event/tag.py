from sqlalchemy import CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.mixins import CreatedAtMixin, SoftDeleteMixin


class Tag(CreatedAtMixin, SoftDeleteMixin, Base):
    """Справочник тегов мероприятий."""

    __tablename__ = "tags"
    __table_args__ = (
        CheckConstraint("title = btrim(title) AND title <> ''", name="title_trimmed"),
        Index(
            "uq_tags_title_lower",
            text("lower(title)"),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        {"comment": "Справочник тегов мероприятий"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, comment="Внутренний идентификатор")
    title: Mapped[str] = mapped_column(String(255), comment="Название тега (без #)")
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        comment="Кто добавил тег; NULL — тег из начального справочника",
    )


class EventTag(Base):
    """Связь мероприятия с тегом."""

    __tablename__ = "event_tags"
    __table_args__ = {"comment": "Теги мероприятия"}

    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), primary_key=True, comment="Мероприятие"
    )
    tag_id: Mapped[int] = mapped_column(
        ForeignKey("tags.id", ondelete="RESTRICT"),
        primary_key=True,
        index=True,
        comment="Тег",
    )
