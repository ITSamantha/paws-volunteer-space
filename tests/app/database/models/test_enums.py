from enum import StrEnum

import pytest
from sqlalchemy import Enum as SAEnum
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Base, enums

ALL_ENUMS = [
    enums.UserStatus,
    enums.ContactType,
    enums.RoleType,
    enums.EventStatus,
    enums.RegistrationStatus,
    enums.BroadcastAudience,
    enums.BroadcastStatus,
    enums.NotificationType,
    enums.NotificationStatus,
]


class TestEnums:
    """Перечисления моделей."""

    @pytest.mark.parametrize("enum_cls", ALL_ENUMS, ids=lambda e: e.__name__)
    def test_values_are_lowercase_snake_case(self, enum_cls: type[StrEnum]) -> None:
        """Значения, которые попадают в БД, написаны строчными с подчёркиваниями."""
        for member in enum_cls:
            assert member.value == member.value.lower()
            assert " " not in member.value

    def test_volunteer_is_not_a_stored_role(self) -> None:
        """Роль волонтёра есть у всех по умолчанию и в БД не хранится."""
        assert "volunteer" not in {role.value for role in enums.RoleType}


def database_type_name(enum_cls: type[StrEnum]) -> str:
    for table in Base.metadata.tables.values():
        for column in table.columns:
            column_type = column.type
            if isinstance(column_type, SAEnum) and column_type.enum_class is enum_cls:
                return str(column_type.name)
    raise LookupError(enum_cls.__name__)


@pytest.mark.integration
class TestEnumsInDatabase:
    """Соответствие enum'ов в коде и в БД."""

    @pytest.mark.parametrize("enum_cls", ALL_ENUMS, ids=lambda e: e.__name__)
    async def test_database_labels_match_code(
        self, session: AsyncSession, enum_cls: type[StrEnum]
    ) -> None:
        """Значения enum-типа в БД совпадают со значениями в коде."""
        rows = await session.execute(
            text(
                "SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
                "WHERE t.typname = :name"
            ),
            {"name": database_type_name(enum_cls)},
        )

        assert {row[0] for row in rows} == {member.value for member in enum_cls}
