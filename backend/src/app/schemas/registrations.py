from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.database.models.enums import RegistrationStatus
from app.schemas.event.base import EventSummary
from app.schemas.fields import Comment


class RegistrationCancel(BaseModel):
    """Отмена своей записи."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    reason: Comment = Field(description="Причина отмены; её увидит организатор")


class RegistrationReject(BaseModel):
    """Отклонение заявки организатором."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    comment: Comment = Field(description="Причина отказа; её увидит волонтёр")


class Attendance(BaseModel):
    """Отметка о посещении."""

    model_config = ConfigDict(extra="forbid")

    attended: bool = Field(description="true — пришёл, false — не пришёл")


class RegistrationBase(BaseModel):
    """Общие поля записи в ответах API."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Внутренний идентификатор записи")
    event_id: int = Field(description="Мероприятие")
    status: RegistrationStatus = Field(
        description=(
            "registered — записан, pending — ждёт одобрения, waitlisted — в листе ожидания, "
            "rejected — отклонён, cancelled — отменена, attended — был, absent — не был"
        )
    )
    created_at: datetime = Field(description="Дата и время записи")
    cancelled_at: datetime | None = Field(description="Дата и время отмены")
    cancellation_reason: str | None = Field(description="Причина отмены")
    decided_at: datetime | None = Field(description="Дата и время решения организатора")
    decision_comment: str | None = Field(description="Комментарий организатора к решению")


class RegistrationRead(RegistrationBase):
    """Запись волонтёра: своя запись."""


class OwnRegistrationRead(RegistrationBase):
    """Своя запись вместе с мероприятием."""

    event: EventSummary = Field(description="Мероприятие")


class ParticipantUser(BaseModel):
    """Волонтёр в списке участников: контакты для организатора."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Внутренний идентификатор")
    telegram_id: int = Field(description="Идентификатор в Telegram")
    telegram_username: str | None = Field(description="Имя пользователя в Telegram")
    full_name: str | None = Field(description="ФИО")
    phone: str = Field(description="Телефон")


class ParticipantRead(RegistrationBase):
    """Запись в списке участников для организатора."""

    user: ParticipantUser = Field(description="Волонтёр")
