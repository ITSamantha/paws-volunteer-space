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

    telegram_id: int = Field(gt=0, description="Идентификатор в Telegram")
    telegram_username: TelegramUsername | None = Field(
        default=None, description="Имя пользователя в Telegram, с @ или без"
    )
    full_name: FullName = Field(description="ФИО")
    phone: Phone = Field(description="Телефон в формате +79991234567", examples=["+79991234567"])
    isu_id: IsuId | None = Field(default=None, description="Номер ИСУ")
    volunteer_id: VolunteerId | None = Field(default=None, description="ID волонтёра на добро.рф")
    vk_link: VkLink | None = Field(default=None, description="Ссылка на профиль ВКонтакте")
    has_notifications_enabled: bool = Field(
        default=True, description="Получать необязательные уведомления и рассылки"
    )
    is_data_processing_allowed: bool = Field(
        description="Согласие на обработку персональных данных; должно быть true"
    )

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

    telegram_username: TelegramUsername | None = Field(
        default=None, description="Имя пользователя в Telegram; null очищает"
    )
    full_name: FullName | None = Field(default=None, description="ФИО")
    phone: Phone | None = Field(default=None, description="Телефон в формате +79991234567")
    isu_id: IsuId | None = Field(default=None, description="Номер ИСУ; null очищает")
    volunteer_id: VolunteerId | None = Field(
        default=None, description="ID волонтёра на добро.рф; null очищает"
    )
    vk_link: VkLink | None = Field(
        default=None, description="Ссылка на профиль ВКонтакте; null очищает"
    )
    has_notifications_enabled: bool | None = Field(
        default=None, description="Получать необязательные уведомления и рассылки"
    )

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

    id: int = Field(description="Внутренний идентификатор")
    telegram_id: int = Field(description="Идентификатор в Telegram")
    telegram_username: str | None = Field(description="Имя пользователя в Telegram")
    full_name: str | None = Field(description="ФИО")
    phone: str = Field(description="Телефон")
    isu_id: str | None = Field(description="Номер ИСУ")
    volunteer_id: str | None = Field(description="ID волонтёра на добро.рф")
    vk_link: str | None = Field(description="Ссылка на профиль ВКонтакте")
    status: UserStatus = Field(description="Статус: active или blocked")
    comment: str | None = Field(
        description="Комментарий, например причина блокировки; виден только организаторам и админам"
    )
    has_notifications_enabled: bool = Field(
        description="Включены необязательные уведомления и рассылки"
    )
    is_data_processing_allowed: bool = Field(
        description="Дано согласие на обработку персональных данных"
    )
    roles: list[RoleType] = Field(description="Дополнительные роли; пусто — обычный волонтёр")
    created_at: datetime = Field(description="Дата и время регистрации")

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

    comment: Comment = Field(description="Причина блокировки")


class UnblockRequest(BaseModel):
    """Запрос на разблокировку; комментарий необязателен."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    comment: Comment | None = Field(default=None, description="Комментарий к разблокировке")


@dataclass(frozen=True)
class UserFilters:
    """Фильтры поиска пользователей."""

    status: UserStatus | None = None
    role: RoleType | None = None
    full_name: str | None = None
    phone: str | None = None
