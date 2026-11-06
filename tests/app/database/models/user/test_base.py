from app.database.models import User
from tests.app.database.models.conftest import CheckNames, TableOf


class TestUser:
    """Таблица users."""

    def test_external_identifiers_are_unique(self, table_of: TableOf) -> None:
        """Telegram ID, номер ИСУ и ID волонтёра уникальны."""
        unique_columns = {column.name for column in table_of(User).columns if column.unique}

        assert {"telegram_id", "isu_id", "volunteer_id"} <= unique_columns

    def test_blocking_requires_comment(self, check_names: CheckNames) -> None:
        """Заблокировать пользователя без комментария (причины) нельзя."""
        assert "ck_users_blocked_requires_comment" in check_names(User)

    def test_roles_are_not_stored_in_users(self, table_of: TableOf) -> None:
        """Роли хранятся в отдельной таблице, а не в колонке пользователя."""
        assert "role" not in table_of(User).columns

    def test_phone_is_required(self, table_of: TableOf) -> None:
        """Номер телефона обязателен."""
        assert table_of(User).columns["phone"].nullable is False

    def test_vk_link_is_optional(self, table_of: TableOf) -> None:
        """Имя пользователя ВКонтакте необязательно."""
        assert table_of(User).columns["vk_link"].nullable is True

    def test_phone_must_have_valid_format(self, check_names: CheckNames) -> None:
        """Телефон хранится в международном формате: +, затем 10-15 цифр."""
        assert "ck_users_phone_format" in check_names(User)
