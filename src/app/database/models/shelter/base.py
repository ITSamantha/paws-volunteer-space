from sqlalchemy import String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.mixins import SoftDeleteMixin, TimestampMixin
from app.database.models.shelter.contact import ShelterContact


class Shelter(TimestampMixin, SoftDeleteMixin, Base):
    """Приют, в который проходят выезды."""

    __tablename__ = "shelters"
    __table_args__ = {"comment": "Справочник приютов"}

    id: Mapped[int] = mapped_column(primary_key=True, comment="Внутренний идентификатор")
    title: Mapped[str] = mapped_column(String(255), comment="Название приюта")
    address: Mapped[str] = mapped_column(String(500), comment="Адрес приюта")
    instructions: Mapped[str | None] = mapped_column(
        comment="Стандартные требования приюта (сменная одежда, ограничения и т. п.)"
    )
    is_approval_required: Mapped[bool] = mapped_column(
        server_default=text("false"),
        comment="Нужно ли одобрять записи; значение по умолчанию для новых мероприятий приюта",
    )

    contacts: Mapped[list[ShelterContact]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )
