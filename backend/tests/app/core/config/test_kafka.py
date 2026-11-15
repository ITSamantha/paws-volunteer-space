import pytest

from app.core.config import KafkaSettings


class TestKafkaSettings:
    """Настройки публикации событий для бота."""

    def test_kafka_is_disabled_by_default(self) -> None:
        """По умолчанию Kafka выключена: локально и в тестах брокер не нужен."""
        settings = KafkaSettings(_env_file=None)

        assert settings.is_enabled is False
        assert settings.notifications_topic == "paws.notifications"
        assert settings.bootstrap_servers == "localhost:9092"

    def test_values_come_from_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Настройки читаются из переменных KAFKA_*."""
        monkeypatch.setenv("KAFKA_IS_ENABLED", "true")
        monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
        monkeypatch.setenv("KAFKA_NOTIFICATIONS_TOPIC", "custom")

        settings = KafkaSettings(_env_file=None)

        assert settings.is_enabled is True
        assert settings.bootstrap_servers == "kafka:9092"
        assert settings.notifications_topic == "custom"
