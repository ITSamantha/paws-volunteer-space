from typing import ClassVar


class AppError(Exception):
    """Ожидаемая ошибка бизнес-логики, которую API превращает в понятный ответ."""

    status_code: ClassVar[int] = 400
    code: ClassVar[str] = "bad_request"

    def __init__(self, message: str) -> None:
        """Сохраняет сообщение, которое увидит клиент."""
        super().__init__(message)
        self.message = message


class UnauthorizedError(AppError):
    """Не удалось определить, кто обращается (401)."""

    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    """Действие запрещено (403)."""

    status_code = 403
    code = "forbidden"


class NotFoundError(AppError):
    """Объект не найден (404)."""

    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    """Действие конфликтует с текущим состоянием данных (409)."""

    status_code = 409
    code = "conflict"
