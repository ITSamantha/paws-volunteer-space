from app.database.models import UserRole
from tests.app.database.models.conftest import TableOf


class TestUserRole:
    """Таблица user_roles."""

    def test_primary_key_is_user_and_role(self, table_of: TableOf) -> None:
        """Одному пользователю нельзя выдать одну и ту же роль дважды."""
        primary_key = table_of(UserRole).primary_key

        assert list(primary_key.columns.keys()) == ["user_id", "role"]

    def test_roles_are_deleted_together_with_user(self, table_of: TableOf) -> None:
        """При удалении пользователя его роли удаляются каскадом."""
        foreign_key = next(iter(table_of(UserRole).columns["user_id"].foreign_keys))

        assert foreign_key.ondelete == "CASCADE"

    def test_granting_user_cannot_be_deleted_while_roles_exist(self, table_of: TableOf) -> None:
        """Нельзя удалить пользователя, который выдал роли: автор должен сохраняться."""
        foreign_key = next(iter(table_of(UserRole).columns["granted_by"].foreign_keys))

        assert foreign_key.ondelete == "RESTRICT"
