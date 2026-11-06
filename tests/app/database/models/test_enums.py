from enum import StrEnum

import pytest

from app.database.models import enums

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
