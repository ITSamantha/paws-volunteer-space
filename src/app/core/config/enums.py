from enum import StrEnum


class AppEnv(StrEnum):
    LOCAL = "local"
    STAGING = "staging"
    PRODUCTION = "production"
