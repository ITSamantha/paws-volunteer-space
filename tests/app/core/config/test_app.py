import pytest
from pydantic import ValidationError

from app.core.config import AppEnv
from tests.app.core.config.conftest import AppSettingsFactory


class TestAppSettings:
    """Общие настройки приложения."""

    def test_defaults_are_safe(self, make_app_settings: AppSettingsFactory) -> None:
        """По умолчанию отладка выключена."""
        settings = make_app_settings()

        assert settings.env is AppEnv.LOCAL
        assert settings.is_debug is False

    @pytest.mark.parametrize(
        ("env", "expected"),
        [(AppEnv.PRODUCTION, True), (AppEnv.STAGING, False), (AppEnv.LOCAL, False)],
    )
    def test_is_production(
        self, make_app_settings: AppSettingsFactory, env: AppEnv, expected: bool
    ) -> None:
        """Признак production истинен только для окружения production."""
        assert make_app_settings(env=env).is_production is expected

    @pytest.mark.parametrize(
        ("env", "is_debug", "expected"),
        [
            (AppEnv.LOCAL, True, True),
            (AppEnv.LOCAL, False, False),
            (AppEnv.STAGING, True, True),
            (AppEnv.PRODUCTION, True, False),
            (AppEnv.PRODUCTION, False, False),
        ],
    )
    def test_debug_is_never_enabled_in_production(
        self, make_app_settings: AppSettingsFactory, env: AppEnv, is_debug: bool, expected: bool
    ) -> None:
        """Отладка (документация API, SQL-логи) не включается в production даже флагом."""
        assert make_app_settings(env=env, is_debug=is_debug).is_debug_enabled is expected

    def test_settings_are_immutable(self, make_app_settings: AppSettingsFactory) -> None:
        """Настройки нельзя изменить после создания."""
        settings = make_app_settings()

        with pytest.raises(ValidationError):
            settings.__setattr__("is_debug", True)

    def test_values_are_read_from_prefixed_environment_variables(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Значения берутся из переменных APP_*."""
        from app.core.config import AppSettings

        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("APP_LOG_LEVEL", "WARNING")

        settings = AppSettings(_env_file=None)

        assert settings.env is AppEnv.PRODUCTION
        assert settings.log_level == "WARNING"
