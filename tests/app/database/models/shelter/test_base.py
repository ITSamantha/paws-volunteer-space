from app.database.models import Shelter
from tests.app.database.models.conftest import TableOf


class TestShelter:
    """Таблица shelters."""

    def test_has_instructions(self, table_of: TableOf) -> None:
        """Требования приюта хранятся в колонке instructions и необязательны."""
        column = table_of(Shelter).columns["instructions"]

        assert column.nullable is True

    def test_contacts_are_not_stored_in_shelter(self, table_of: TableOf) -> None:
        """Контакты лежат в отдельной таблице, а не в колонках приюта."""
        columns = table_of(Shelter).columns

        assert "contact" not in columns
        assert "contacts" not in columns

    def test_name_and_address_are_required(self, table_of: TableOf) -> None:
        """Название и адрес обязательны."""
        columns = table_of(Shelter).columns

        assert columns["title"].nullable is False
        assert columns["address"].nullable is False
