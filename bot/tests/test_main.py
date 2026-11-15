import runpy
from unittest.mock import AsyncMock, patch


class TestMain:
    """Точка входа python -m bot."""

    def test_module_starts_the_application(self) -> None:
        """Запуск модуля запускает приложение."""
        with patch("bot.app.Application.run", new=AsyncMock()) as run:
            runpy.run_module("bot", run_name="__main__")

        run.assert_awaited_once()
