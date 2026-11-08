import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers import Routers


class TestApplication:
    """Сборка приложения."""

    def test_all_routers_are_included(self, app: FastAPI) -> None:
        """Маршруты всех роутеров доступны в приложении."""
        paths = set(app.openapi()["paths"])

        assert paths >= {"/health", "/health/ready"}

    def test_routers_are_registered(self) -> None:
        """В реестре есть хотя бы один роутер."""
        assert Routers.all()


class TestDocs:
    """Документация API."""

    @pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
    def test_docs_are_disabled_by_default(self, client: TestClient, path: str) -> None:
        """Без режима отладки документация и схема API недоступны."""
        assert client.get(path).status_code == 404
