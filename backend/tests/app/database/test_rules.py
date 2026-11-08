from sqlalchemy import Table

from app.database.models import Base
from app.database.rules import NamingConvention


def table(name: str) -> Table:
    return Base.metadata.tables[name]


class TestNamingConvention:
    """Соглашение об именах ограничений и индексов."""

    def test_covers_all_constraint_kinds(self) -> None:
        """Шаблоны заданы для индексов, уникальных, check, внешних и первичных ключей."""
        assert set(NamingConvention.PATTERNS) == {"ix", "uq", "ck", "fk", "pk"}

    def test_primary_key_name(self) -> None:
        """Имя первичного ключа строится из имени таблицы."""
        assert table("users").primary_key.name == "pk_users"

    def test_foreign_key_name(self) -> None:
        """Имя внешнего ключа включает таблицу, колонку и целевую таблицу."""
        names = {constraint.name for constraint in table("events").foreign_key_constraints}

        assert "fk_events_created_by_users" in names

    def test_unique_constraint_name(self) -> None:
        """Имя уникального ограничения строится из таблицы и колонки."""
        names = {constraint.name for constraint in table("users").constraints}

        assert "uq_users_telegram_id" in names
