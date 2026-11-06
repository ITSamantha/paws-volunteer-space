from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, PgEnum
from app.database.models.enums import ContactType


class ShelterContact(Base):
    __tablename__ = "shelter_contacts"
    __table_args__ = (
        UniqueConstraint(
            "shelter_id", "type", "value", name="uq_shelter_contacts_shelter_id_type_value"
        ),
        CheckConstraint("btrim(value) <> ''", name="value_not_empty"),
        {"comment": "Контакты приютов"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, comment="Внутренний идентификатор")
    shelter_id: Mapped[int] = mapped_column(
        ForeignKey("shelters.id", ondelete="CASCADE"), comment="Приют"
    )
    type: Mapped[ContactType] = mapped_column(
        PgEnum.create(ContactType, "contact_type"), comment="Тип контакта"
    )
    value: Mapped[str] = mapped_column(String(500), comment="Значение контакта")
