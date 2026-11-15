from dataclasses import dataclass
from datetime import datetime
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.database.models.enums import EventStatus
from app.schemas.base.titles import TitleRead
from app.schemas.fields import (
    Capacity,
    Comment,
    Description,
    HttpLink,
    Instructions,
    Location,
    TelegramLink,
    Title,
)
from app.schemas.partial import PartialUpdate


class EventCreate(BaseModel):
    """Данные для создания мероприятия."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: Title = Field(description="Название мероприятия")
    description: Description | None = Field(default=None, description="Описание и формат")
    starts_at: AwareDatetime = Field(description="Начало, с часовым поясом; должно быть в будущем")
    ends_at: AwareDatetime | None = Field(default=None, description="Окончание, позже начала")
    shelter_id: int | None = Field(default=None, gt=0, description="Приют, если мероприятие в нём")
    location: Location | None = Field(
        default=None, description="Место встречи; без него используется адрес приюта"
    )
    capacity: Capacity = Field(description="Лимит участников")
    is_approval_required: bool | None = Field(
        default=None,
        description="Одобрять записи вручную; если не указано, берётся значение приюта",
    )
    instructions: Instructions | None = Field(
        default=None,
        description="Что взять с собой; если не указано, берутся требования приюта",
    )
    comment: Description | None = Field(default=None, description="Прочая информация")
    event_link: HttpLink | None = Field(default=None, description="Ссылка на добро.рф")
    telegram_chat_link: TelegramLink | None = Field(
        default=None, description="Чат участников; виден только подтверждённым"
    )
    bonus_ids: list[int] = Field(default_factory=list, max_length=20, description="Бонусы")
    tag_ids: list[int] = Field(default_factory=list, max_length=20, description="Теги")

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        """Окончание позже начала; нужно место или приют."""
        if self.ends_at is not None and self.ends_at <= self.starts_at:
            raise ValueError("окончание должно быть позже начала")

        if self.location is None and self.shelter_id is None:
            raise ValueError("укажите приют или место встречи")

        return self


class EventUpdate(PartialUpdate):
    """Изменяемые поля мероприятия; переданные заменяются, null очищает необязательные."""

    required_fields = (
        "title",
        "starts_at",
        "capacity",
        "is_approval_required",
        "bonus_ids",
        "tag_ids",
    )

    title: Title | None = Field(default=None, description="Название мероприятия")
    description: Description | None = Field(default=None, description="Описание; null очищает")
    starts_at: AwareDatetime | None = Field(default=None, description="Начало; в будущем")
    ends_at: AwareDatetime | None = Field(default=None, description="Окончание; null очищает")
    shelter_id: int | None = Field(default=None, gt=0, description="Приют; null убирает")
    location: Location | None = Field(default=None, description="Место встречи; null очищает")
    capacity: Capacity | None = Field(default=None, description="Лимит участников")
    is_approval_required: bool | None = Field(default=None, description="Одобрять записи")
    instructions: Instructions | None = Field(default=None, description="Что взять; null очищает")
    comment: Description | None = Field(default=None, description="Прочее; null очищает")
    event_link: HttpLink | None = Field(
        default=None, description="Ссылка на добро.рф; null очищает"
    )
    telegram_chat_link: TelegramLink | None = Field(
        default=None, description="Чат участников; null очищает"
    )
    bonus_ids: list[int] | None = Field(
        default=None, max_length=20, description="Бонусы целиком; [] убирает все"
    )
    tag_ids: list[int] | None = Field(
        default=None, max_length=20, description="Теги целиком; [] убирает все"
    )


class EventCancel(BaseModel):
    """Отмена мероприятия."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    reason: Comment = Field(description="Причина отмены; её увидят участники")


class EventShelter(BaseModel):
    """Приют мероприятия в кратком виде."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Внутренний идентификатор приюта")
    title: str = Field(description="Название приюта")
    address: str = Field(description="Адрес приюта")


class EventOrganizer(BaseModel):
    """Организатор мероприятия: контакт для связи."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Внутренний идентификатор")
    full_name: str | None = Field(description="ФИО")
    telegram_username: str | None = Field(description="Имя пользователя в Telegram")


class EventSummary(BaseModel):
    """Мероприятие в списке."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Внутренний идентификатор")
    title: str = Field(description="Название мероприятия")
    starts_at: datetime = Field(description="Начало")
    ends_at: datetime | None = Field(description="Окончание")
    shelter: EventShelter | None = Field(description="Приют")
    location: str | None = Field(description="Место встречи; без него — адрес приюта")
    capacity: int = Field(description="Лимит участников")
    occupied: int = Field(default=0, description="Сколько мест занято")
    is_approval_required: bool = Field(description="Записи одобряются вручную")
    status: EventStatus = Field(description="Статус: planned, cancelled или completed")
    bonuses: list[TitleRead] = Field(description="Бонусы за участие")
    tags: list[TitleRead] = Field(description="Теги")


class EventRead(EventSummary):
    """Карточка мероприятия."""

    description: str | None = Field(description="Описание и формат")
    cancellation_reason: str | None = Field(description="Причина отмены")
    instructions: str | None = Field(description="Что взять с собой, требования приюта")
    comment: str | None = Field(description="Прочая информация")
    event_link: str | None = Field(description="Ссылка на добро.рф")
    telegram_chat_link: str | None = Field(
        description="Чат участников; null, если нет ссылки или запись ещё не подтверждена"
    )
    organizer: EventOrganizer = Field(
        validation_alias="creator", description="Организатор: контакт для связи"
    )
    created_by: int = Field(description="Организатор, создавший мероприятие")
    created_at: datetime = Field(description="Дата и время создания")


@dataclass(frozen=True)
class EventFilters:
    """Фильтры списка мероприятий."""

    status: EventStatus | None = None
    shelter_id: int | None = None
    starts_from: datetime | None = None
    starts_to: datetime | None = None
    tag_id: int | None = None
    bonus_id: int | None = None
