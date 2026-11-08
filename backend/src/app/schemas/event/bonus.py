from pydantic import BaseModel, ConfigDict, Field

from app.schemas.fields import Title


class BonusCreate(BaseModel):
    """Новый бонус."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: Title = Field(description="Название бонуса", examples=["ПГАС"])
