from collections.abc import Callable
from typing import Any

import pytest
from pydantic import SecretStr

from app.core.config import AppSettings, DatabaseSettings

AppSettingsFactory = Callable[..., AppSettings]
DatabaseSettingsFactory = Callable[..., DatabaseSettings]


@pytest.fixture
def make_app_settings() -> AppSettingsFactory:
    def factory(**overrides: Any) -> AppSettings:
        return AppSettings(_env_file=None, **overrides)

    return factory


@pytest.fixture
def make_database_settings() -> DatabaseSettingsFactory:
    def factory(**overrides: Any) -> DatabaseSettings:
        values: dict[str, Any] = {
            "db": "db",
            "user": "user",
            "password": SecretStr("secret"),
        }
        values.update(overrides)
        return DatabaseSettings(_env_file=None, **values)

    return factory
