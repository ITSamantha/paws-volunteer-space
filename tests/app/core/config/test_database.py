import pytest
from pydantic import SecretStr, ValidationError

from tests.app.core.config.conftest import DatabaseSettingsFactory


class TestDatabaseSettings:
    """Настройки подключения к БД."""

    def test_url_uses_asyncpg_driver(self, make_database_settings: DatabaseSettingsFactory) -> None:
        """URL БД использует асинхронный драйвер asyncpg."""
        assert make_database_settings().url.drivername == "postgresql+asyncpg"

    def test_url_escapes_special_characters_in_password(
        self, make_database_settings: DatabaseSettingsFactory
    ) -> None:
        """Спецсимволы в пароле экранируются и не ломают URL."""
        raw_value = "p@ss:/w%rd"
        settings = make_database_settings(password=SecretStr(raw_value))

        url = settings.url

        assert url.password == raw_value
        assert "p%40ss%3A%2Fw%25rd" in url.render_as_string(hide_password=False)

    def test_password_is_hidden_in_repr(
        self, make_database_settings: DatabaseSettingsFactory
    ) -> None:
        """Пароль не попадает в repr и str настроек, а значит и в логи."""
        settings = make_database_settings(password=SecretStr("top-secret-value"))

        assert "top-secret-value" not in repr(settings)
        assert "top-secret-value" not in str(settings)

    @pytest.mark.parametrize("port", [0, 65536, -1])
    def test_invalid_port_is_rejected(
        self, make_database_settings: DatabaseSettingsFactory, port: int
    ) -> None:
        """Порт вне диапазона 1-65535 отклоняется."""
        with pytest.raises(ValidationError):
            make_database_settings(port=port)

    def test_settings_are_immutable(self, make_database_settings: DatabaseSettingsFactory) -> None:
        """Настройки нельзя изменить после создания."""
        settings = make_database_settings()

        with pytest.raises(ValidationError):
            settings.__setattr__("host", "elsewhere")

    def test_values_are_read_from_prefixed_environment_variables(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Значения берутся из переменных POSTGRES_*."""
        from app.core.config import DatabaseSettings

        monkeypatch.setenv("POSTGRES_DB", "from_env")
        monkeypatch.setenv("POSTGRES_USER", "env_user")
        monkeypatch.setenv("POSTGRES_PASSWORD", "env_password")

        settings = DatabaseSettings(_env_file=None)

        assert (settings.db, settings.user) == ("from_env", "env_user")
