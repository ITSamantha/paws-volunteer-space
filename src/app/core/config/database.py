from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="POSTGRES_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    host: str = "localhost"
    port: int = Field(default=5432, ge=1, le=65535)
    db: str
    user: str
    password: SecretStr

    @property
    def url(self) -> URL:
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.user,
            password=self.password.get_secret_value(),
            host=self.host,
            port=self.port,
            database=self.db,
        )
