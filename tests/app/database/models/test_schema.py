import pytest
from sqlalchemy import Table
from sqlalchemy.orm import configure_mappers

from app.database import models
from app.database.models import Base

EXPECTED_TABLES = {
    "users",
    "user_roles",
    "shelters",
    "shelter_contacts",
    "events",
    "bonuses",
    "event_bonuses",
    "tags",
    "event_tags",
    "registrations",
    "broadcasts",
    "notifications",
}

ALL_TABLES = Base.metadata.sorted_tables


class TestSchema:
    """Общие свойства схемы БД."""

    def test_all_tables_are_registered(self) -> None:
        """Все ожидаемые таблицы есть в metadata."""
        assert set(Base.metadata.tables) == EXPECTED_TABLES

    def test_every_exported_model_is_mapped(self) -> None:
        """Каждая экспортируемая модель попала в metadata."""
        exported = [getattr(models, name) for name in models.__all__ if name != "Base"]

        assert {model.__tablename__ for model in exported} == EXPECTED_TABLES

    def test_mappers_are_configurable(self) -> None:
        """Связи между моделями корректны (нет неоднозначных FK и опечаток)."""
        configure_mappers()

    @pytest.mark.parametrize("table", ALL_TABLES, ids=lambda t: t.name)
    def test_table_has_comment(self, table: Table) -> None:
        """У каждой таблицы есть комментарий."""
        assert table.comment

    @pytest.mark.parametrize("table", ALL_TABLES, ids=lambda t: t.name)
    def test_every_column_has_comment(self, table: Table) -> None:
        """У каждой колонки есть комментарий."""
        missing = [column.name for column in table.columns if not column.comment]

        assert not missing

    @pytest.mark.parametrize("table", ALL_TABLES, ids=lambda t: t.name)
    def test_constraints_have_explicit_names(self, table: Table) -> None:
        """У всех ограничений есть имена, миграции получаются детерминированными."""
        unnamed = [constraint for constraint in table.constraints if constraint.name is None]

        assert not unnamed

    @pytest.mark.parametrize("table", ALL_TABLES, ids=lambda t: t.name)
    def test_primary_key_is_defined(self, table: Table) -> None:
        """У каждой таблицы есть первичный ключ."""
        assert table.primary_key.columns.keys()
