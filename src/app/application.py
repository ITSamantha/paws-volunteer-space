import logging

from fastapi import FastAPI

from app.api.routers import Routers
from app.core.config import Settings
from app.core.lifespan import Lifespan


class Application:
    """Сборка приложения FastAPI."""

    @staticmethod
    def create() -> FastAPI:
        settings = Settings.get()
        logging.basicConfig(level=settings.app.log_level.upper())

        docs_enabled = settings.app.is_debug_enabled
        app = FastAPI(
            title="Paw Volunteer Space",
            lifespan=Lifespan.run,
            docs_url="/docs" if docs_enabled else None,
            redoc_url=None,
            openapi_url="/openapi.json" if docs_enabled else None,
        )
        for router in Routers.all():
            app.include_router(router)
        return app
