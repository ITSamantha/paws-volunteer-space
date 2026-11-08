import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import Database

logger = logging.getLogger(__name__)


class HealthRouter:
    """Служебные эндпоинты для проверки живости и готовности."""

    @staticmethod
    async def liveness() -> dict[str, str]:
        return {"status": "ok"}

    @staticmethod
    async def readiness(
        session: Annotated[AsyncSession, Depends(Database.session)],
    ) -> dict[str, str]:
        try:
            await session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            logger.exception("Database readiness check failed")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="database unavailable"
            ) from None
        return {"status": "ok"}

    @classmethod
    def build(cls) -> APIRouter:
        router = APIRouter(tags=["service"])
        router.add_api_route("/health", cls.liveness, methods=["GET"])
        router.add_api_route("/health/ready", cls.readiness, methods=["GET"])
        return router
