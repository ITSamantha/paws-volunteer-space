from functools import lru_cache
from typing import Self

from pydantic import BaseModel, ConfigDict, Field

from app.core.config.app import AppSettings
from app.core.config.auth import AuthSettings
from app.core.config.database import DatabaseSettings
from app.core.config.kafka import KafkaSettings


class Settings(BaseModel):
    """Все настройки приложения."""

    model_config = ConfigDict(frozen=True)

    app: AppSettings = Field(default_factory=AppSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)

    @classmethod
    @lru_cache
    def get(cls) -> Self:
        """Возвращает настройки; читаются один раз за процесс."""
        return cls()
