from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.config.enums import AppEnv


class AppSettings(BaseSettings):
    """Окружение, режим отладки и уровень логирования (переменные APP_*)."""

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    env: AppEnv = AppEnv.LOCAL
    is_debug: bool = False
    log_level: str = "INFO"

    @property
    def is_production(self) -> bool:
        """Приложение запущено в промышленном окружении."""
        return self.env is AppEnv.PRODUCTION

    @property
    def is_debug_enabled(self) -> bool:
        """Отладка включена; в промышленном окружении всегда выключена."""
        return self.is_debug and not self.is_production
