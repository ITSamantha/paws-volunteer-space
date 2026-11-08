from app.database.models import Bonus, EventBonus
from tests.app.database.models.conftest import CheckNames, TableOf


class TestBonus:
    """Справочник бонусов."""

    def test_title_is_unique_ignoring_case(self, table_of: TableOf) -> None:
        """Название уникально без учёта регистра."""
        index_names = {index.name for index in table_of(Bonus).indexes}

        assert "uq_bonuses_title_lower" in index_names

    def test_title_must_be_trimmed(self, check_names: CheckNames) -> None:
        """Название не пустое и без пробелов по краям."""
        assert "ck_bonuses_title_trimmed" in check_names(Bonus)

    def test_creator_is_optional(self, table_of: TableOf) -> None:
        """У бонуса из начального справочника нет автора."""
        assert table_of(Bonus).c.created_by.nullable


class TestEventBonus:
    """Связь мероприятий с бонусами."""

    def test_primary_key_is_pair(self, table_of: TableOf) -> None:
        """Бонус нельзя привязать к мероприятию дважды."""
        assert set(table_of(EventBonus).primary_key.columns.keys()) == {"event_id", "bonus_id"}
