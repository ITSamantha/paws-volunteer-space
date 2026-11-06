from app.database.models import Event
from tests.app.database.models.conftest import CheckNames, TableOf


class TestEvent:
    """Таблица events."""

    def test_capacity_must_be_positive(self, check_names: CheckNames) -> None:
        """Лимит участников должен быть больше нуля."""
        assert "ck_events_capacity_positive" in check_names(Event)

    def test_end_must_be_after_start(self, check_names: CheckNames) -> None:
        """Окончание не может быть раньше начала."""
        assert "ck_events_ends_after_start" in check_names(Event)

    def test_contact_is_taken_from_organizer(self, table_of: TableOf) -> None:
        """Отдельных контактов у мероприятия нет: их берут у организатора (created_by)."""
        columns = table_of(Event).columns

        assert "contact" not in columns
        assert columns["created_by"].nullable is False

    def test_comment_is_optional(self, table_of: TableOf) -> None:
        """Прочая информация о мероприятии необязательна."""
        assert table_of(Event).columns["comment"].nullable is True
