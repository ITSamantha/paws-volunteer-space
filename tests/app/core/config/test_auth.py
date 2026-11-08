import pytest
from pydantic import ValidationError

from app.core.config import AuthSettings


class TestAuthSettings:
    """Настройки авторизации."""

    def test_token_is_read_from_arguments(self) -> None:
        """Токен бота задаётся настройкой."""
        settings = AuthSettings(_env_file=None, bot_token="x" * 32)

        assert settings.bot_token.get_secret_value() == "x" * 32

    def test_short_token_is_rejected(self) -> None:
        """Слишком короткий токен отклоняется: его легко подобрать."""
        with pytest.raises(ValidationError):
            AuthSettings(_env_file=None, bot_token="x" * 31)

    def test_token_is_hidden_in_repr(self) -> None:
        """Токен не попадает в repr и str настроек, а значит и в логи."""
        settings = AuthSettings(_env_file=None, bot_token="super-secret-token-" + "x" * 20)

        assert "super-secret-token" not in repr(settings)
        assert "super-secret-token" not in str(settings)

    def test_token_is_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Без токена приложение не стартует."""
        monkeypatch.delenv("AUTH_BOT_TOKEN", raising=False)

        with pytest.raises(ValidationError):
            AuthSettings(_env_file=None)
