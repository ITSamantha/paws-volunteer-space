from app.database.models import EventTag, Tag
from tests.app.database.models.conftest import CheckNames, TableOf


class TestTag:
    """Справочник тегов."""

    def test_title_is_unique_ignoring_case(self, table_of: TableOf) -> None:
        """Название уникально без учёта регистра."""
        index_names = {index.name for index in table_of(Tag).indexes}

        assert "uq_tags_title_lower" in index_names

    def test_title_must_be_trimmed(self, check_names: CheckNames) -> None:
        """Название не пустое и без пробелов по краям."""
        assert "ck_tags_title_trimmed" in check_names(Tag)

    def test_creator_is_optional(self, table_of: TableOf) -> None:
        """У тега из начального справочника нет автора."""
        assert table_of(Tag).c.created_by.nullable


class TestEventTag:
    """Связь мероприятий с тегами."""

    def test_primary_key_is_pair(self, table_of: TableOf) -> None:
        """Тег нельзя привязать к мероприятию дважды."""
        assert set(table_of(EventTag).primary_key.columns.keys()) == {"event_id", "tag_id"}
