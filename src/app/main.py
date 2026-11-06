import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.database.session import Database

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await Database.engine().dispose()


def create_app() -> FastAPI:
    settings = Settings.get()
    logging.basicConfig(level=settings.app.log_level.upper())

    docs_enabled = settings.app.is_debug_enabled
    app = FastAPI(
        title="Paw Volunteer Space",
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    @app.get("/health", tags=["service"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["service"])
    async def ready(session: Annotated[AsyncSession, Depends(Database.session)]) -> dict[str, str]:
        try:
            await session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            logger.exception("Database readiness check failed")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="database unavailable"
            ) from None
        return {"status": "ok"}

    return app


app = create_app()
