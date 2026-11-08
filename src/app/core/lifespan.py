from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database.session import Database


class Lifespan:
    """Жизненный цикл приложения: что освободить при остановке."""

    @staticmethod
    @asynccontextmanager
    async def run(_: FastAPI) -> AsyncIterator[None]:
        yield

        await Database.engine().dispose()
