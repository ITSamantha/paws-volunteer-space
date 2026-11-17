from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.database.models.enums import BroadcastAudience, BroadcastStatus
from app.schemas.fields import Comment
from app.schemas.partial import PartialUpdate


class BroadcastCreate(BaseModel):
    """Новая рассылка. Сохраняется черновиком, никому не отправляется."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    text: Comment = Field(description="Текст сообщения")
    audience: BroadcastAudience = Field(description="Кому адресована рассылка")
    event_id: int | None = Field(
        default=None,
        gt=0,
        description="Мероприятие; нужно только для аудитории «участники мероприятия»",
    )

    @model_validator(mode="after")
    def _event_matches_audience(self) -> Self:
        """Мероприятие указывают ровно тогда, когда аудитория — его участники."""
        needs_event = self.audience is BroadcastAudience.EVENT_PARTICIPANTS

        if needs_event != (self.event_id is not None):
            raise ValueError("мероприятие нужно только для аудитории «участники мероприятия»")

        return self


class BroadcastUpdate(PartialUpdate):
    """Правка черновика."""

    text: Comment | None = Field(default=None, description="Текст сообщения")
    audience: BroadcastAudience | None = Field(default=None, description="Кому адресована рассылка")
    event_id: int | None = Field(
        default=None, gt=0, description="Мероприятие для аудитории «участники мероприятия»"
    )

    required_fields = ("text", "audience")


class BroadcastRead(BaseModel):
    """Рассылка в ответах API."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Внутренний идентификатор")
    author_id: int = Field(description="Автор")
    text: str = Field(description="Текст сообщения")
    audience: BroadcastAudience = Field(description="Кому адресована рассылка")
    event_id: int | None = Field(description="Мероприятие, если аудитория — его участники")
    status: BroadcastStatus = Field(description="Черновик, в очереди или отправлена")
    sent_at: datetime | None = Field(description="Когда отправлена")
    created_at: datetime = Field(description="Когда создана")
