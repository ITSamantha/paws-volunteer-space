from typing import ClassVar, Self

from pydantic import BaseModel, ConfigDict, model_validator


class PartialUpdate(BaseModel):
    """Частичное изменение: переданные поля заменяются, null очищает необязательные."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    required_fields: ClassVar[tuple[str, ...]] = ()

    @model_validator(mode="after")
    def _required_fields_cannot_be_cleared(self) -> Self:
        """Обязательные поля нельзя очистить значением null."""
        cleared = [
            name
            for name in self.required_fields
            if name in self.model_fields_set and getattr(self, name) is None
        ]

        if cleared:
            raise ValueError(f"поля нельзя очистить: {', '.join(cleared)}")

        return self
