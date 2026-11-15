import pytest
from pydantic import ValidationError

from bot.config import DatabaseSettings, KafkaSettings, QueueSettings, Settings, TelegramSettings


class TestSettings:
    """Настройки бота."""

    def test_database_url_matches_the_api(self) -> None:
        """База та же, что у API: те же переменные POSTGRES_*, драйвер asyncpg."""
        settings = DatabaseSettings(
            _env_file=None, db="d", user="u", password="p", host="h", port=6000
        )

        url = settings.url

        assert url.drivername == "postgresql+asyncpg"
        assert (url.host, url.port, url.database, url.username) == ("h", 6000, "d", "u")
        assert url.password == "p"

    def test_database_password_is_hidden(self) -> None:
        """Пароль не попадает в repr настроек."""
        settings = DatabaseSettings(_env_file=None, db="d", user="u", password="secret-pass")

        assert "secret-pass" not in repr(settings)

    def test_short_telegram_token_is_rejected(self) -> None:
        """Слишком короткий токен отклоняется."""
        with pytest.raises(ValidationError):
            TelegramSettings(_env_file=None, bot_token="short")

    def test_kafka_defaults(self) -> None:
        """Топик по умолчанию совпадает с топиком API."""
        settings = KafkaSettings(_env_file=None)

        assert settings.notifications_topic == "paws.notifications"
        assert settings.group_id == "paws-bot"

    def test_queue_defaults(self) -> None:
        """Разумные значения очереди по умолчанию."""
        settings = QueueSettings(_env_file=None)

        assert settings.max_attempts == 5
        assert settings.send_interval > 0

    def test_settings_are_read_once(self) -> None:
        """Настройки читаются из окружения один раз за процесс."""
        Settings.get.cache_clear()

        first = Settings.get()
        second = Settings.get()

        assert first is second
        assert first.database.db
        assert first.telegram.bot_token.get_secret_value()
        assert first.app.timezone == "Europe/Moscow"
