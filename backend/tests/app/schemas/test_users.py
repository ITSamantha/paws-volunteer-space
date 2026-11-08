from typing import Any

import pytest
from pydantic import ValidationError

from app.database.models.enums import RoleType
from app.schemas.users import UserCreate, UserRead, UserUpdate

VALID: dict[str, Any] = {
    "telegram_id": 100,
    "full_name": "Иванов Иван Иванович",
    "phone": "+79991234567",
    "is_data_processing_allowed": True,
}


class TestUserCreate:
    """Данные для регистрации волонтёра."""

    def test_minimal_data_is_valid(self) -> None:
        """Достаточно Telegram ID, ФИО, телефона и согласия на обработку данных."""
        user = UserCreate(**VALID)

        assert user.has_notifications_enabled is True
        assert user.isu_id is None

    def test_consent_is_required(self) -> None:
        """Без согласия на обработку персональных данных зарегистрироваться нельзя."""
        with pytest.raises(ValidationError):
            UserCreate(**{**VALID, "is_data_processing_allowed": False})

    @pytest.mark.parametrize("phone", ["89991234567", "+7 999 123 45 67", "+123456789", "+7abc"])
    def test_invalid_phone_is_rejected(self, phone: str) -> None:
        """Телефон должен быть в международном формате."""
        with pytest.raises(ValidationError):
            UserCreate(**{**VALID, "phone": phone})

    def test_telegram_username_loses_at_sign(self) -> None:
        """Ведущий @ в имени пользователя Telegram убирается."""
        user = UserCreate(**{**VALID, "telegram_username": "@paw_user"})

        assert user.telegram_username == "paw_user"

    @pytest.mark.parametrize("username", ["abc", "bad name", "кириллица"])
    def test_invalid_telegram_username_is_rejected(self, username: str) -> None:
        """Имя пользователя Telegram: 5–32 латинских символа, цифры и подчёркивание."""
        with pytest.raises(ValidationError):
            UserCreate(**{**VALID, "telegram_username": username})

    @pytest.mark.parametrize(
        "link", ["https://vk.com/id1", "https://vk.ru/paw", "http://m.vk.com/paw_club"]
    )
    def test_vk_profile_links_are_accepted(self, link: str) -> None:
        """Ссылки на профили ВКонтакте принимаются."""
        assert UserCreate(**{**VALID, "vk_link": link}).vk_link == link

    @pytest.mark.parametrize(
        "link", ["https://example.com/id1", "vk.com/id1", "https://vk.com/", "javascript:alert(1)"]
    )
    def test_other_links_are_rejected(self, link: str) -> None:
        """Ссылки не на профиль ВКонтакте отклоняются."""
        with pytest.raises(ValidationError):
            UserCreate(**{**VALID, "vk_link": link})

    @pytest.mark.parametrize("isu_id", ["12a", "", "12345678901234567"])
    def test_invalid_isu_id_is_rejected(self, isu_id: str) -> None:
        """Номер ИСУ состоит из цифр, не длиннее 16."""
        with pytest.raises(ValidationError):
            UserCreate(**{**VALID, "isu_id": isu_id})

    def test_text_is_stripped(self) -> None:
        """Пробелы по краям значений обрезаются."""
        user = UserCreate(**{**VALID, "full_name": "  Иванов Иван  "})

        assert user.full_name == "Иванов Иван"

    def test_unknown_fields_are_rejected(self) -> None:
        """Лишние поля не принимаются: нельзя, например, передать роль или статус."""
        with pytest.raises(ValidationError):
            UserCreate(**{**VALID, "status": "blocked"})

    def test_telegram_id_must_be_positive(self) -> None:
        """Telegram ID положительный."""
        with pytest.raises(ValidationError):
            UserCreate(**{**VALID, "telegram_id": 0})


class TestUserUpdate:
    """Данные для изменения профиля."""

    def test_empty_update_is_valid(self) -> None:
        """Пустое изменение допустимо и ничего не меняет."""
        assert UserUpdate().model_dump(exclude_unset=True) == {}

    def test_optional_field_can_be_cleared(self) -> None:
        """Необязательное поле можно очистить, передав null."""
        update = UserUpdate(vk_link=None)

        assert update.model_dump(exclude_unset=True) == {"vk_link": None}

    @pytest.mark.parametrize("field", ["full_name", "phone", "has_notifications_enabled"])
    def test_required_field_cannot_be_cleared(self, field: str) -> None:
        """Обязательные поля очистить нельзя."""
        with pytest.raises(ValidationError):
            UserUpdate(**{field: None})


class TestUserRead:
    """Ответ с профилем пользователя."""

    def test_roles_may_be_given_as_plain_values(self) -> None:
        """Роли принимаются как обычные значения, а не только как объекты БД."""
        user = UserRead.model_validate(
            {
                "id": 1,
                "telegram_id": 100,
                "telegram_username": None,
                "full_name": None,
                "phone": "+79991234567",
                "isu_id": None,
                "volunteer_id": None,
                "vk_link": None,
                "status": "active",
                "comment": None,
                "has_notifications_enabled": True,
                "is_data_processing_allowed": True,
                "roles": ["admin"],
                "created_at": "2026-11-08T10:00:00+00:00",
            }
        )

        assert user.roles == [RoleType.ADMIN]

    def test_roles_must_be_a_list(self) -> None:
        """Роли обязаны быть списком."""
        with pytest.raises(ValidationError):
            UserRead.model_validate({"roles": "admin"})
