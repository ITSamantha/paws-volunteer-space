from sqlalchemy import UniqueConstraint

from app.database.models import Broadcast, Registration
from tests.app.database.models.conftest import CheckNames, TableOf


class TestRegistrationConstraints:
    """Ограничения таблицы registrations."""

    def test_user_cannot_register_twice_for_one_event(self, table_of: TableOf) -> None:
        """Пара (мероприятие, пользователь) уникальна."""
        uniques = [
            constraint
            for constraint in table_of(Registration).constraints
            if isinstance(constraint, UniqueConstraint)
        ]

        assert [list(c.columns.keys()) for c in uniques] == [["event_id", "user_id"]]

    def test_cancellation_requires_reason(self, check_names: CheckNames) -> None:
        """У отменённой записи обязательна причина."""
        assert "ck_registrations_cancelled_requires_reason" in check_names(Registration)


class TestBroadcastConstraints:
    """Ограничения таблицы broadcasts."""

    def test_event_is_required_only_for_event_participants(self, check_names: CheckNames) -> None:
        """Мероприятие указывается тогда и только тогда, когда аудитория — его участники."""
        assert "ck_broadcasts_event_matches_audience" in check_names(Broadcast)
