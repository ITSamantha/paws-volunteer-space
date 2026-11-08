from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import AppError


class ErrorHandlers:
    """Единый формат ошибок: {"code": ..., "message": ...}."""

    @staticmethod
    async def app_error(_: Request, error: AppError) -> JSONResponse:
        """Превращает ожидаемую ошибку приложения в JSON-ответ."""
        return JSONResponse(
            status_code=error.status_code,
            content={"code": error.code, "message": error.message},
        )

    @classmethod
    def register(cls, app: FastAPI) -> None:
        """Подключает обработчики ошибок к приложению."""
        app.exception_handler(AppError)(cls.app_error)
