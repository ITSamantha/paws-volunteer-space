import pytest
from fastapi.testclient import TestClient


class TestHealth:
    """Служебные эндпоинты."""

    def test_liveness_returns_ok(self, client: TestClient) -> None:
        """Liveness отвечает 200 без обращения к БД."""
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @pytest.mark.usefixtures("healthy_database")
    def test_readiness_returns_ok_when_database_is_available(self, client: TestClient) -> None:
        """Readiness отвечает 200, если БД доступна."""
        response = client.get("/health/ready")

        assert response.status_code == 200

    @pytest.mark.usefixtures("broken_database")
    def test_readiness_returns_503_when_database_is_down(self, client: TestClient) -> None:
        """Readiness отвечает 503, если БД недоступна."""
        response = client.get("/health/ready")

        assert response.status_code == 503

    @pytest.mark.usefixtures("broken_database")
    def test_readiness_does_not_leak_database_details(self, client: TestClient) -> None:
        """В ответе об ошибке нет хоста и пользователя БД."""
        response = client.get("/health/ready")

        assert "secret_user" not in response.text
        assert "db.internal" not in response.text
