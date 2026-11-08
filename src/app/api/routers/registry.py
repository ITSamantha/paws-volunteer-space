from fastapi import APIRouter

from app.api.routers.health import HealthRouter


class Routers:
    """Все роутеры приложения. Новый роутер добавляется сюда."""

    @staticmethod
    def all() -> tuple[APIRouter, ...]:
        return (HealthRouter.build(),)
