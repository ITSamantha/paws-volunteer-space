from datetime import datetime

from sqlalchemy import DateTime

from app.database.base import Base, PgEnum
from app.database.models.enums import UserStatus
from app.database.rules import NamingConvention


class TestBase:
    """Базовый класс моделей."""

    def test_naming_convention_is_applied_to_metadata(self) -> None:
        """Соглашение об именах ограничений подключено к metadata."""
        assert Base.metadata.naming_convention == NamingConvention.PATTERNS

    def test_datetime_is_timezone_aware(self) -> None:
        """Все datetime хранятся как timestamptz."""
        column_type = Base.type_annotation_map[datetime]

        assert isinstance(column_type, DateTime)
        assert column_type.timezone is True


class TestPgEnum:
    """Хелпер нативных PostgreSQL enum."""

    def test_stores_values_not_names(self) -> None:
        """В БД попадают значения членов enum, а не их имена."""
        enum_type = PgEnum.create(UserStatus, "user_status")

        assert enum_type.enums == ["active", "blocked"]

    def test_is_native_postgres_enum(self) -> None:
        """Тип создаётся как нативный enum с заданным именем."""
        enum_type = PgEnum.create(UserStatus, "user_status")

        assert enum_type.native_enum is True
        assert enum_type.name == "user_status"
