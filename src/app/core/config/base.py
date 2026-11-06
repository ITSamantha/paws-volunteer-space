from functools import lru_cache
from typing import Self

from pydantic import BaseModel, ConfigDict, Field

from app.core.config.app import AppSettings
from app.core.config.database import DatabaseSettings


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    app: AppSettings = Field(default_factory=AppSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)

    @classmethod
    @lru_cache
    def get(cls) -> Self:
        return cls()
