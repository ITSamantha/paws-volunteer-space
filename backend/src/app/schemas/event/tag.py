from pydantic import BaseModel, ConfigDict, Field

from app.schemas.fields import TagTitle


class TagCreate(BaseModel):
    """Новый тег."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: TagTitle = Field(
        description="Название тега; ведущий # отбрасывается", examples=["Собаки"]
    )
