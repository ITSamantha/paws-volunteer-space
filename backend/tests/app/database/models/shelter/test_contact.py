from sqlalchemy import UniqueConstraint

from app.database.models import ShelterContact
from app.database.models.enums import ContactType
from tests.app.database.models.conftest import CheckNames, TableOf


class TestShelterContact:
    """Таблица shelter_contacts."""

    def test_contacts_are_deleted_together_with_shelter(self, table_of: TableOf) -> None:
        """При удалении приюта его контакты удаляются каскадом."""
        foreign_key = next(iter(table_of(ShelterContact).columns["shelter_id"].foreign_keys))

        assert foreign_key.ondelete == "CASCADE"

    def test_same_contact_cannot_be_added_twice(self, table_of: TableOf) -> None:
        """Один и тот же контакт нельзя добавить приюту дважды."""
        uniques = [
            constraint
            for constraint in table_of(ShelterContact).constraints
            if isinstance(constraint, UniqueConstraint)
        ]

        assert [list(c.columns.keys()) for c in uniques] == [["shelter_id", "type", "value"]]

    def test_value_must_not_be_empty(self, check_names: CheckNames) -> None:
        """Пустое значение контакта (в том числе из пробелов) недопустимо."""
        assert "ck_shelter_contacts_value_not_empty" in check_names(ShelterContact)

    def test_supports_common_contact_types(self) -> None:
        """Поддерживаются телефон, почта, сайт, ВК, Telegram и прочее."""
        assert {"phone", "email", "website", "vk", "telegram", "other"} <= {
            contact_type.value for contact_type in ContactType
        }
