from pydantic_settings import BaseSettings, SettingsConfigDict


class KafkaSettings(BaseSettings):
    """Публикация событий для бота в Kafka (переменные KAFKA_*)."""

    model_config = SettingsConfigDict(
        env_prefix="KAFKA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    is_enabled: bool = False
    bootstrap_servers: str = "localhost:9092"
    notifications_topic: str = "paws.notifications"
