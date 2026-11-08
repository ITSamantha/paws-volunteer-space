from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import AppError
from app.schemas.errors import ErrorResponse


class ErrorHandlers:
    """Единый формат ошибок: {"code": ..., "message": ...}."""

    @staticmethod
    async def app_error(_: Request, error: AppError) -> JSONResponse:
        """Превращает ожидаемую ошибку приложения в JSON-ответ."""
        body = ErrorResponse(code=error.code, message=error.message)

        return JSONResponse(status_code=error.status_code, content=body.model_dump())

    @classmethod
    def register(cls, app: FastAPI) -> None:
        """Подключает обработчики ошибок к приложению."""
        app.exception_handler(AppError)(cls.app_error)
