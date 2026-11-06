from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.mixins import SoftDeleteMixin, TimestampMixin
from app.database.models.shelter.contact import ShelterContact


class Shelter(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "shelters"
    __table_args__ = {"comment": "Справочник приютов"}

    id: Mapped[int] = mapped_column(primary_key=True, comment="Внутренний идентификатор")
    title: Mapped[str] = mapped_column(String(255), comment="Название приюта")
    address: Mapped[str] = mapped_column(String(500), comment="Адрес приюта")
    instructions: Mapped[str | None] = mapped_column(
        comment="Стандартные требования приюта (сменная одежда, ограничения и т. п.)"
    )

    contacts: Mapped[list[ShelterContact]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )
