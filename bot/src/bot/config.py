from functools import lru_cache
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class TelegramSettings(BaseSettings):
    """Доступ к Telegram (переменные TELEGRAM_*)."""

    model_config = SettingsConfigDict(
        env_prefix="TELEGRAM_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    bot_token: SecretStr = Field(min_length=10)


class KafkaSettings(BaseSettings):
    """Чтение событий из Kafka (переменные KAFKA_*)."""

    model_config = SettingsConfigDict(
        env_prefix="KAFKA_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    bootstrap_servers: str = "localhost:9092"
    notifications_topic: str = "paws.notifications"
    group_id: str = "paws-bot"


class DatabaseSettings(BaseSettings):
    """Подключение к PostgreSQL; те же переменные POSTGRES_*, что и у API."""

    model_config = SettingsConfigDict(
        env_prefix="POSTGRES_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    host: str = "localhost"
    port: int = Field(default=5432, ge=1, le=65535)
    db: str
    user: str
    password: SecretStr

    @property
    def url(self) -> URL:
        """URL подключения для асинхронного драйвера asyncpg."""
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.user,
            password=self.password.get_secret_value(),
            host=self.host,
            port=self.port,
            database=self.db,
        )


class QueueSettings(BaseSettings):
    """Очередь доставки (переменные QUEUE_*)."""

    model_config = SettingsConfigDict(
        env_prefix="QUEUE_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    send_interval: float = Field(default=0.05, ge=0)
    calm_period: float = Field(default=1.0, gt=0)
    max_attempts: int = Field(default=5, ge=1)
    retry_delay: float = Field(default=60.0, ge=0)
    keep_finished_days: int = Field(default=7, ge=1)


class AppSettings(BaseSettings):
    """Общие настройки (переменные BOT_*)."""

    model_config = SettingsConfigDict(
        env_prefix="BOT_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    timezone: str = "Europe/Moscow"
    log_level: str = "INFO"


class Settings(BaseModel):
    """Все настройки бота."""

    model_config = ConfigDict(frozen=True)

    app: AppSettings = Field(default_factory=AppSettings)
    telegram: TelegramSettings = Field(default_factory=TelegramSettings)
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    queue: QueueSettings = Field(default_factory=QueueSettings)

    @classmethod
    @lru_cache
    def get(cls) -> Self:
        """Настройки читаются один раз за процесс."""
        return cls()
