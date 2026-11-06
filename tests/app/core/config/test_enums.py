import pytest

from app.core.config import AppEnv


class TestAppEnv:
    """Окружения приложения."""

    @pytest.mark.parametrize(
        ("member", "value"),
        [
            (AppEnv.LOCAL, "local"),
            (AppEnv.STAGING, "staging"),
            (AppEnv.PRODUCTION, "production"),
        ],
    )
    def test_values_match_environment_variable(self, member: AppEnv, value: str) -> None:
        """Значения совпадают с тем, что пишут в APP_ENV."""
        assert member.value == value

    def test_can_be_created_from_string(self) -> None:
        """Строка из переменной окружения превращается в член enum."""
        assert AppEnv("production") is AppEnv.PRODUCTION
