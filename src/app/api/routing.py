from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, ClassVar, TypeVar

from fastapi import APIRouter, params

from app.core.exceptions import AppError
from app.schemas.errors import ErrorResponse

Handler = TypeVar("Handler", bound=Callable[..., Any])
Errors = Sequence[type[AppError]]


@dataclass(frozen=True)
class RouteSpec:
    """Описание эндпоинта, заданное декоратором."""

    method: str
    path: str
    summary: str
    response: Any
    status_code: int | None
    errors: Errors


class Route:
    """Декораторы эндпоинтов: HTTP-метод, путь и описание задаются над обработчиком.

    Декоратор ставится ближе всего к функции, под @classmethod или @staticmethod.
    Подробное описание берётся из докстринга, схема ответа — из response,
    ошибки — из перечисленных исключений.
    """

    SPECS: ClassVar[dict[Callable[..., Any], RouteSpec]] = {}

    @classmethod
    def get(
        cls,
        path: str = "",
        *,
        summary: str,
        response: Any = None,
        status_code: int | None = None,
        errors: Errors = (),
    ) -> Callable[[Handler], Handler]:
        """Эндпоинт GET."""
        return cls.__register("GET", path, summary, response, status_code, errors)

    @classmethod
    def post(
        cls,
        path: str = "",
        *,
        summary: str,
        response: Any = None,
        status_code: int | None = None,
        errors: Errors = (),
    ) -> Callable[[Handler], Handler]:
        """Эндпоинт POST."""
        return cls.__register("POST", path, summary, response, status_code, errors)

    @classmethod
    def put(
        cls,
        path: str = "",
        *,
        summary: str,
        response: Any = None,
        status_code: int | None = None,
        errors: Errors = (),
    ) -> Callable[[Handler], Handler]:
        """Эндпоинт PUT."""
        return cls.__register("PUT", path, summary, response, status_code, errors)

    @classmethod
    def patch(
        cls,
        path: str = "",
        *,
        summary: str,
        response: Any = None,
        status_code: int | None = None,
        errors: Errors = (),
    ) -> Callable[[Handler], Handler]:
        """Эндпоинт PATCH."""
        return cls.__register("PATCH", path, summary, response, status_code, errors)

    @classmethod
    def delete(
        cls,
        path: str = "",
        *,
        summary: str,
        response: Any = None,
        status_code: int | None = None,
        errors: Errors = (),
    ) -> Callable[[Handler], Handler]:
        """Эндпоинт DELETE."""
        return cls.__register("DELETE", path, summary, response, status_code, errors)

    @classmethod
    def __register(
        cls,
        method: str,
        path: str,
        summary: str,
        response: Any,
        status_code: int | None,
        errors: Errors,
    ) -> Callable[[Handler], Handler]:
        """Запоминает описание эндпоинта; сама функция не меняется."""

        def decorator(handler: Handler) -> Handler:
            cls.SPECS[handler] = RouteSpec(method, path, summary, response, status_code, errors)

            return handler

        return decorator


class BaseRouter:
    """Базовый класс роутеров: эндпоинты собираются из методов с декораторами Route."""

    prefix: ClassVar[str] = ""
    tags: ClassVar[Sequence[str]] = ()
    dependencies: ClassVar[Sequence[params.Depends]] = ()
    errors: ClassVar[Errors] = ()

    @classmethod
    def build(cls) -> APIRouter:
        """Собирает роутер; эндпоинты регистрируются в порядке объявления методов."""
        router = APIRouter(
            prefix=cls.prefix,
            tags=list(cls.tags),
            dependencies=cls.dependencies,
        )

        for name, member in vars(cls).items():
            handler = member.__func__ if isinstance(member, classmethod | staticmethod) else member
            spec = Route.SPECS.get(handler)

            if spec is None:
                continue

            options: dict[str, Any] = {}

            if spec.response is not None:
                options["response_model"] = spec.response

            router.add_api_route(
                spec.path,
                getattr(cls, name),
                methods=[spec.method],
                summary=spec.summary,
                status_code=spec.status_code,
                responses=cls.__responses([*cls.errors, *spec.errors]),
                **options,
            )

        return router

    @staticmethod
    def __responses(errors: Errors) -> dict[int | str, dict[str, Any]]:
        """Описание ответов с ошибками в документации API."""
        responses: dict[int | str, dict[str, Any]] = {}

        for error in errors:
            responses[error.status_code] = {
                "model": ErrorResponse,
                "description": (error.__doc__ or "").strip(),
            }

        return responses
