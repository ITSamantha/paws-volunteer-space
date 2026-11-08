from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.database.models.enums import ContactType
from app.schemas.fields import Address, ContactValue, Instructions, Title
from app.schemas.partial import PartialUpdate


class ContactCreate(BaseModel):
    """Новый контакт приюта."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    type: ContactType = Field(description="Тип контакта")
    value: ContactValue = Field(
        description="Значение: номер, адрес, ссылка", examples=["+78125550000"]
    )


class ContactRead(BaseModel):
    """Контакт приюта в ответах API."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Внутренний идентификатор")
    type: ContactType = Field(description="Тип контакта")
    value: str = Field(description="Значение контакта")


class ShelterCreate(BaseModel):
    """Данные для добавления приюта."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: Title = Field(description="Название приюта")
    address: Address = Field(description="Адрес приюта")
    instructions: Instructions | None = Field(
        default=None, description="Требования приюта: сменная одежда, ограничения и т. п."
    )
    is_approval_required: bool = Field(
        default=False,
        description="Одобрять записи вручную; значение по умолчанию для новых мероприятий приюта",
    )
    contacts: list[ContactCreate] = Field(
        default_factory=list, max_length=20, description="Контакты приюта"
    )

    @model_validator(mode="after")
    def _contacts_are_unique(self) -> Self:
        """Один и тот же контакт нельзя указать дважды."""
        pairs = [(contact.type, contact.value) for contact in self.contacts]

        if len(pairs) != len(set(pairs)):
            raise ValueError("контакты не должны повторяться")

        return self


class ShelterUpdate(PartialUpdate):
    """Изменяемые поля приюта; контакты меняются отдельными запросами."""

    required_fields = ("title", "address", "is_approval_required")

    title: Title | None = Field(default=None, description="Название приюта")
    address: Address | None = Field(default=None, description="Адрес приюта")
    instructions: Instructions | None = Field(
        default=None, description="Требования приюта; null очищает"
    )
    is_approval_required: bool | None = Field(
        default=None, description="Одобрять записи вручную по умолчанию"
    )


class ShelterRead(BaseModel):
    """Приют в ответах API."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Внутренний идентификатор")
    title: str = Field(description="Название приюта")
    address: str = Field(description="Адрес приюта")
    instructions: str | None = Field(description="Требования приюта")
    is_approval_required: bool = Field(
        description="Записи по умолчанию одобряются вручную организатором"
    )
    contacts: list[ContactRead] = Field(description="Контакты приюта")
    created_at: datetime = Field(description="Дата и время добавления")
