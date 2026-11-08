from dataclasses import dataclass
from datetime import datetime
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.database.models.enums import RoleType, UserStatus
from app.schemas.fields import (
    Comment,
    FullName,
    IsuId,
    Phone,
    TelegramUsername,
    VkLink,
    VolunteerId,
)


class UserCreate(BaseModel):
    """Данные для регистрации волонтёра."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    telegram_id: int = Field(gt=0)
    telegram_username: TelegramUsername | None = None
    full_name: FullName
    phone: Phone
    isu_id: IsuId | None = None
    volunteer_id: VolunteerId | None = None
    vk_link: VkLink | None = None
    has_notifications_enabled: bool = True
    is_data_processing_allowed: bool

    @field_validator("is_data_processing_allowed")
    @classmethod
    def _consent_is_required(cls, value: bool) -> bool:
        """Без согласия на обработку персональных данных регистрация невозможна."""
        if not value:
            raise ValueError("для регистрации нужно согласие на обработку персональных данных")

        return value


class UserUpdate(BaseModel):
    """Изменяемые поля профиля; переданные поля заменяются, null очищает необязательные."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    telegram_username: TelegramUsername | None = None
    full_name: FullName | None = None
    phone: Phone | None = None
    isu_id: IsuId | None = None
    volunteer_id: VolunteerId | None = None
    vk_link: VkLink | None = None
    has_notifications_enabled: bool | None = None

    @model_validator(mode="after")
    def _required_fields_cannot_be_cleared(self) -> Self:
        """Обязательные поля нельзя очистить значением null."""
        required = ("full_name", "phone", "has_notifications_enabled")
        cleared = [
            name
            for name in required
            if name in self.model_fields_set and getattr(self, name) is None
        ]

        if cleared:
            raise ValueError(f"поля нельзя очистить: {', '.join(cleared)}")

        return self


class UserRead(BaseModel):
    """Пользователь в ответах API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_id: int
    telegram_username: str | None
    full_name: str | None
    phone: str
    isu_id: str | None
    volunteer_id: str | None
    vk_link: str | None
    status: UserStatus
    comment: str | None
    has_notifications_enabled: bool
    is_data_processing_allowed: bool
    roles: list[RoleType]
    created_at: datetime

    @field_validator("roles", mode="before")
    @classmethod
    def _roles_as_types(cls, value: object) -> object:
        """Принимает роли как объекты модели и отдаёт их типы."""
        if isinstance(value, list):
            return [getattr(item, "role", item) for item in value]

        return value


class BlockRequest(BaseModel):
    """Запрос на блокировку; комментарий обязателен."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    comment: Comment


class UnblockRequest(BaseModel):
    """Запрос на разблокировку; комментарий необязателен."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    comment: Comment | None = None


@dataclass(frozen=True)
class UserFilters:
    """Фильтры поиска пользователей."""

    status: UserStatus | None = None
    role: RoleType | None = None
    full_name: str | None = None
    phone: str | None = None
