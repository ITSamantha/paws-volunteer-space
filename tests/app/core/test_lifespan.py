from unittest.mock import AsyncMock, patch

from fastapi import FastAPI

from app.core.lifespan import Lifespan


class TestLifespan:
    """Жизненный цикл приложения."""

    async def test_engine_is_disposed_on_shutdown(self) -> None:
        """При остановке приложения соединения с БД закрываются."""
        with patch("app.core.lifespan.Database.engine") as engine:
            engine.return_value.dispose = AsyncMock()

            async with Lifespan.run(FastAPI()):
                engine.return_value.dispose.assert_not_called()

            engine.return_value.dispose.assert_awaited_once()
