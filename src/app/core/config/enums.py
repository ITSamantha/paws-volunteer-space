from enum import StrEnum


class AppEnv(StrEnum):
    """Окружение, в котором запущено приложение."""

    LOCAL = "local"
    STAGING = "staging"
    PRODUCTION = "production"
