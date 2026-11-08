from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    """Токен сервиса (бота) для доступа к API (переменные AUTH_*)."""

    model_config = SettingsConfigDict(
        env_prefix="AUTH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    bot_token: SecretStr = Field(min_length=32)
