from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import AppSettings, DatabaseSettings, Settings


@pytest.fixture
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> pytest.MonkeyPatch:
    monkeypatch.chdir(tmp_path)
    for name in ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


class TestSettings:
    """Корневой объект настроек."""

    def test_composes_sections(self, isolated_env: pytest.MonkeyPatch) -> None:
        """Корневые настройки собирают секции app и database."""
        isolated_env.setenv("POSTGRES_DB", "db")
        isolated_env.setenv("POSTGRES_USER", "user")
        isolated_env.setenv("POSTGRES_PASSWORD", "password")

        settings = Settings()

        assert isinstance(settings.app, AppSettings)
        assert isinstance(settings.database, DatabaseSettings)

    def test_get_is_cached(self) -> None:
        """Settings.get возвращает один и тот же объект."""
        assert Settings.get() is Settings.get()

    @pytest.mark.usefixtures("isolated_env")
    def test_missing_database_variables_fail_fast(self) -> None:
        """Без обязательных переменных БД приложение не стартует."""
        with pytest.raises(ValidationError):
            Settings()
