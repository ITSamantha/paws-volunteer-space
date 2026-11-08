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

        are_docs_enabled = settings.app.is_debug_enabled
        docs_url = "/docs" if are_docs_enabled else None
        redoc_url = None
        openapi_url = "/openapi.json" if are_docs_enabled else None

        app = FastAPI(
            title="Paw Volunteer Space",
            lifespan=Lifespan.run,
            docs_url=docs_url,
            redoc_url=redoc_url,
            openapi_url=openapi_url,
        )

        for router in Routers.all():
            app.include_router(router)

        return app
