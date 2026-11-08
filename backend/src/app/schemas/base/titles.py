from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TitleRead(BaseModel):
    """Запись справочника (бонус или тег) в ответах API."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Внутренний идентификатор")
    title: str = Field(description="Название")
    created_at: datetime = Field(description="Дата и время добавления")
