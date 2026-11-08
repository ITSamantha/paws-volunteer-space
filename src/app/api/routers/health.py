import logging
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routing import BaseRouter, Route
from app.database.session import Database

logger = logging.getLogger(__name__)


class HealthRouter(BaseRouter):
    """Служебные эндпоинты для проверки живости и готовности."""

    tags = ("service",)

    @staticmethod
    @Route.get("/health", summary="Проверка живости", response=dict[str, str])
    async def liveness() -> dict[str, str]:
        """Процесс жив."""
        return {"status": "ok"}

    @staticmethod
    @Route.get("/health/ready", summary="Проверка готовности", response=dict[str, str])
    async def readiness(
        session: Annotated[AsyncSession, Depends(Database.session)],
    ) -> dict[str, str]:
        """Приложение готово принимать запросы: база данных отвечает."""
        try:
            await session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            logger.exception("Database readiness check failed")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="database unavailable"
            ) from None

        return {"status": "ok"}
