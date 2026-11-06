from typing import cast

import pytest
from sqlalchemy import DateTime, Table

from app.database.models import Base, Event, Registration, Shelter, User


def column_names(model: type[Base]) -> list[str]:
    return [column.name for column in cast(Table, model.__table__).columns]


class TestCreatedAtMixin:
    """Миксин с датой создания."""

    @pytest.mark.parametrize("model", [User, Shelter, Event, Registration])
    def test_adds_created_at(self, model: type[Base]) -> None:
        """Колонка created_at есть у всех подключивших миксин моделей."""
        assert "created_at" in column_names(model)

    def test_created_at_is_timezone_aware_and_filled_by_database(self) -> None:
        """Дата создания хранится с поясом и проставляется самой БД."""
        column = cast(Table, User.__table__).columns["created_at"]

        assert isinstance(column.type, DateTime)
        assert column.type.timezone is True
        assert column.server_default is not None
        assert column.nullable is False


class TestTimestampMixin:
    """Миксин с датами создания и изменения."""

    @pytest.mark.parametrize("model", [User, Shelter, Event])
    def test_adds_updated_at(self, model: type[Base]) -> None:
        """Колонка updated_at есть у моделей с TimestampMixin."""
        assert "updated_at" in column_names(model)

    def test_registration_does_not_track_updates(self) -> None:
        """Записи на мероприятие не имеют updated_at: у них только created_at."""
        assert "updated_at" not in column_names(Registration)


class TestSoftDeleteMixin:
    """Миксин мягкого удаления."""

    @pytest.mark.parametrize("model", [User, Shelter])
    def test_adds_nullable_deleted_at(self, model: type[Base]) -> None:
        """deleted_at необязателен: NULL означает, что запись активна."""
        column = cast(Table, model.__table__).columns["deleted_at"]

        assert column.nullable is True

    def test_events_are_not_soft_deleted(self) -> None:
        """У мероприятий нет deleted_at: они отменяются статусом."""
        assert "deleted_at" not in column_names(Event)

    def test_service_columns_are_last_in_table(self) -> None:
        """Служебные колонки идут в конце таблицы, после полей модели."""
        assert column_names(User)[-3:] == ["created_at", "updated_at", "deleted_at"]
