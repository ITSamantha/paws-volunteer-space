from fastapi import APIRouter

from app.api.routers.base.router import BaseRouter
from app.api.routers.event.bonuses import BonusesRouter
from app.api.routers.event.tags import TagsRouter
from app.api.routers.health import HealthRouter
from app.api.routers.shelters import SheltersRouter
from app.api.routers.users import UsersRouter


class Routers:
    """Все роутеры приложения. Новый роутер добавляется сюда."""

    @staticmethod
    def all() -> list[APIRouter]:
        """Собирает все роутеры приложения."""
        routers: list[type[BaseRouter]] = [
            HealthRouter,
            UsersRouter,
            BonusesRouter,
            TagsRouter,
            SheltersRouter,
        ]

        built: list[APIRouter] = []
        for router in routers:
            built.append(router.build())

        return built
