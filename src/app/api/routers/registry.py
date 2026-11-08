from fastapi import APIRouter

from app.api.routers.health import HealthRouter
from app.api.routers.users import UsersRouter


class Routers:
    """Все роутеры приложения. Новый роутер добавляется сюда."""

    @staticmethod
    def all() -> list[APIRouter]:
        """Собирает все роутеры приложения."""
        routers: list[type[HealthRouter] | type[UsersRouter]] = [HealthRouter, UsersRouter]

        built: list[APIRouter] = []
        for router in routers:
            built.append(router.build())

        return built
