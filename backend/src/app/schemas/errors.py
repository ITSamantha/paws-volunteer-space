from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Ошибка в ответе API."""

    code: str = Field(description="Машинный код ошибки", examples=["not_found"])
    message: str = Field(
        description="Сообщение для пользователя", examples=["Пользователь не найден"]
    )
