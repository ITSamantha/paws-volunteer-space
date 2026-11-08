from typing import Any

import pytest
from httpx import AsyncClient

from app.database.models.enums import UserStatus
from tests.app.api.support import as_user, make_admin, make_organizer
from tests.app.database.factory import Factory

pytestmark = pytest.mark.integration

REGISTRATION: dict[str, Any] = {
    "telegram_id": 5001,
    "telegram_username": "@paw_user",
    "full_name": "Иванов Иван Иванович",
    "phone": "+79991234567",
    "isu_id": "123456",
    "volunteer_id": "dobro-1",
    "vk_link": "https://vk.com/id1",
    "is_data_processing_allowed": True,
}


class TestServiceToken:
    """Токен бота (Authorization: Bearer)."""

    async def test_request_without_token_is_unauthorized(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Без токена запрос отклоняется."""
        user = await factory.user()

        response = await api.get(
            f"/api/users/{user.id}", headers={"Authorization": "", **as_user(user)}
        )

        assert response.status_code == 401
        assert response.json()["code"] == "unauthorized"

    @pytest.mark.parametrize("header", ["Bearer wrong-token", "Basic abc", "Bearer ", "token"])
    async def test_wrong_token_is_unauthorized(
        self, api: AsyncClient, factory: Factory, header: str
    ) -> None:
        """Чужой токен и неверный формат заголовка отклоняются."""
        user = await factory.user()

        response = await api.get(
            f"/api/users/{user.id}", headers={"Authorization": header, **as_user(user)}
        )

        assert response.status_code == 401

    async def test_registration_requires_token(self, api: AsyncClient) -> None:
        """Регистрация тоже доступна только боту."""
        response = await api.post("/api/users", json=REGISTRATION, headers={"Authorization": ""})

        assert response.status_code == 401

    async def test_token_is_checked_before_user(self, api: AsyncClient) -> None:
        """Сначала проверяется токен: без него нельзя даже узнать, есть ли такой пользователь."""
        response = await api.get(
            "/api/users/by-telegram/42",
            headers={"Authorization": "", "X-Telegram-Id": "42"},
        )

        assert response.status_code == 401

    async def test_health_does_not_require_token(self, api: AsyncClient) -> None:
        """Проверка живости доступна без токена."""
        response = await api.get("/health", headers={"Authorization": ""})

        assert response.status_code == 200


class TestRegistration:
    """POST /api/users: регистрация волонтёра."""

    async def test_volunteer_is_registered(self, api: AsyncClient) -> None:
        """Волонтёр регистрируется и получает профиль без ролей."""
        response = await api.post("/api/users", json=REGISTRATION)

        body = response.json()
        assert response.status_code == 201
        assert body["telegram_id"] == 5001
        assert body["telegram_username"] == "paw_user"
        assert body["status"] == "active"
        assert body["roles"] == []
        assert body["has_notifications_enabled"] is True
        assert body["comment"] is None

    async def test_registered_user_can_be_found_by_telegram_id(self, api: AsyncClient) -> None:
        """После регистрации бот находит пользователя по Telegram ID."""
        await api.post("/api/users", json=REGISTRATION)

        response = await api.get("/api/users/by-telegram/5001", headers={"X-Telegram-Id": "5001"})

        assert response.status_code == 200
        assert response.json()["full_name"] == "Иванов Иван Иванович"

    async def test_consent_is_required(self, api: AsyncClient) -> None:
        """Без согласия на обработку данных регистрация отклоняется."""
        response = await api.post(
            "/api/users", json={**REGISTRATION, "is_data_processing_allowed": False}
        )

        assert response.status_code == 422

    @pytest.mark.parametrize("field", ["status", "roles", "comment", "id"])
    async def test_service_fields_cannot_be_set(self, api: AsyncClient, field: str) -> None:
        """Статус, роли и комментарий при регистрации задать нельзя."""
        response = await api.post("/api/users", json={**REGISTRATION, field: "admin"})

        assert response.status_code == 422

    async def test_duplicate_telegram_id_is_conflict(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Повторная регистрация того же Telegram ID — конфликт."""
        existing = await factory.user()

        response = await api.post(
            "/api/users", json={**REGISTRATION, "telegram_id": existing.telegram_id}
        )

        assert response.status_code == 409
        assert response.json()["code"] == "conflict"

    async def test_duplicate_isu_id_is_conflict(self, api: AsyncClient, factory: Factory) -> None:
        """Номер ИСУ принадлежит только одному пользователю."""
        await factory.user(isu_id="123456")

        response = await api.post("/api/users", json=REGISTRATION)

        assert response.status_code == 409
        assert "ИСУ" in response.json()["message"]

    async def test_duplicate_volunteer_id_is_conflict(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """ID на добро.рф принадлежит только одному пользователю."""
        await factory.user(volunteer_id="dobro-1")

        response = await api.post("/api/users", json=REGISTRATION)

        assert response.status_code == 409

    async def test_conflict_does_not_break_following_requests(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """После конфликта можно зарегистрировать другого пользователя."""
        existing = await factory.user()
        await api.post("/api/users", json={**REGISTRATION, "telegram_id": existing.telegram_id})

        response = await api.post("/api/users", json=REGISTRATION)

        assert response.status_code == 201

    async def test_deleted_user_cannot_register_again(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Удалённый пользователь занимает свой Telegram ID: заново зарегистрироваться нельзя."""
        user = await factory.user(telegram_id=5001)
        await api.delete(f"/api/users/{user.id}", headers=as_user(user))

        response = await api.post("/api/users", json=REGISTRATION)

        assert response.status_code == 409


class TestGettingUsers:
    """GET /api/users/{id} и /api/users/by-telegram/{telegram_id}."""

    async def test_user_sees_own_profile(self, api: AsyncClient, factory: Factory) -> None:
        """Пользователь видит свой профиль."""
        user = await factory.user()

        response = await api.get(f"/api/users/{user.id}", headers=as_user(user))

        assert response.status_code == 200
        assert response.json()["id"] == user.id

    async def test_volunteer_cannot_see_other_profile(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Чужой профиль волонтёру недоступен."""
        user = await factory.user()
        stranger = await factory.user()

        response = await api.get(f"/api/users/{user.id}", headers=as_user(stranger))

        assert response.status_code == 403

    async def test_organizer_sees_any_profile(self, api: AsyncClient, factory: Factory) -> None:
        """Организатор видит чужие профили."""
        admin = await make_admin(factory)
        organizer = await make_organizer(factory, admin)
        user = await factory.user()

        response = await api.get(f"/api/users/{user.id}", headers=as_user(organizer))

        assert response.status_code == 200

    async def test_unknown_user_is_not_found(self, api: AsyncClient, factory: Factory) -> None:
        """Несуществующий пользователь — 404."""
        admin = await make_admin(factory)

        response = await api.get("/api/users/999999", headers=as_user(admin))

        assert response.status_code == 404
        assert response.json()["code"] == "not_found"

    async def test_header_is_required(self, api: AsyncClient, factory: Factory) -> None:
        """Без заголовка X-Telegram-Id запрос отклоняется."""
        user = await factory.user()

        response = await api.get(f"/api/users/{user.id}")

        assert response.status_code == 401

    async def test_unregistered_user_is_unauthorized(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Незарегистрированный пользователь не может выполнять действия."""
        user = await factory.user()

        response = await api.get(f"/api/users/{user.id}", headers={"X-Telegram-Id": "777"})

        assert response.status_code == 401

    async def test_blocked_user_cannot_act(self, api: AsyncClient, factory: Factory) -> None:
        """Заблокированный пользователь не может выполнять действия."""
        user = await factory.user(status=UserStatus.BLOCKED, comment="Нарушение")

        response = await api.get(f"/api/users/{user.id}", headers=as_user(user))

        assert response.status_code == 403

    async def test_deleted_user_is_not_found(self, api: AsyncClient, factory: Factory) -> None:
        """Мягко удалённого пользователя не видно."""
        admin = await make_admin(factory)
        user = await factory.user()
        await api.delete(f"/api/users/{user.id}", headers=as_user(admin))

        response = await api.get(f"/api/users/{user.id}", headers=as_user(admin))

        assert response.status_code == 404

    async def test_telegram_lookup_of_missing_user_is_not_found(self, api: AsyncClient) -> None:
        """Бот узнаёт, что пользователь ещё не зарегистрирован: 404."""
        response = await api.get("/api/users/by-telegram/42", headers={"X-Telegram-Id": "42"})

        assert response.status_code == 404

    async def test_telegram_lookup_of_other_user_requires_staff(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Искать чужой Telegram ID может только персонал."""
        user = await factory.user()
        stranger = await factory.user()

        response = await api.get(
            f"/api/users/by-telegram/{user.telegram_id}", headers=as_user(stranger)
        )

        assert response.status_code == 403

    async def test_staff_finds_user_by_telegram_id(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Администратор находит пользователя по Telegram ID."""
        admin = await make_admin(factory)
        user = await factory.user()

        response = await api.get(
            f"/api/users/by-telegram/{user.telegram_id}", headers=as_user(admin)
        )

        assert response.json()["id"] == user.id

    async def test_blocked_user_sees_own_status_without_comment(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Заблокированный видит свой статус, но не внутренний комментарий о причине."""
        user = await factory.user(status=UserStatus.BLOCKED, comment="Внутренняя причина")

        response = await api.get(
            f"/api/users/by-telegram/{user.telegram_id}", headers=as_user(user)
        )

        body = response.json()
        assert body["status"] == "blocked"
        assert body["comment"] is None

    async def test_staff_sees_block_comment(self, api: AsyncClient, factory: Factory) -> None:
        """Организаторы и администраторы видят причину блокировки."""
        admin = await make_admin(factory)
        user = await factory.user(status=UserStatus.BLOCKED, comment="Нарушение правил")

        response = await api.get(f"/api/users/{user.id}", headers=as_user(admin))

        assert response.json()["comment"] == "Нарушение правил"


class TestUpdate:
    """PATCH /api/users/{id}: изменение профиля."""

    async def test_user_updates_own_profile(self, api: AsyncClient, factory: Factory) -> None:
        """Пользователь меняет свои данные."""
        user = await factory.user()

        response = await api.patch(
            f"/api/users/{user.id}",
            json={"full_name": "Петров Пётр", "has_notifications_enabled": False},
            headers=as_user(user),
        )

        body = response.json()
        assert response.status_code == 200
        assert body["full_name"] == "Петров Пётр"
        assert body["has_notifications_enabled"] is False

    async def test_optional_field_is_cleared_by_null(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Необязательное поле очищается значением null."""
        user = await factory.user(vk_link="https://vk.com/id1")

        response = await api.patch(
            f"/api/users/{user.id}", json={"vk_link": None}, headers=as_user(user)
        )

        assert response.json()["vk_link"] is None

    async def test_unspecified_fields_are_kept(self, api: AsyncClient, factory: Factory) -> None:
        """Поля, которых нет в запросе, не меняются."""
        user = await factory.user(vk_link="https://vk.com/id1")

        response = await api.patch(
            f"/api/users/{user.id}", json={"full_name": "Новое Имя"}, headers=as_user(user)
        )

        assert response.json()["vk_link"] == "https://vk.com/id1"

    async def test_required_field_cannot_be_cleared(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Телефон очистить нельзя."""
        user = await factory.user()

        response = await api.patch(
            f"/api/users/{user.id}", json={"phone": None}, headers=as_user(user)
        )

        assert response.status_code == 422

    async def test_status_cannot_be_changed_here(self, api: AsyncClient, factory: Factory) -> None:
        """Статус и комментарий через профиль не меняются."""
        user = await factory.user()

        response = await api.patch(
            f"/api/users/{user.id}", json={"status": "blocked"}, headers=as_user(user)
        )

        assert response.status_code == 422

    async def test_other_user_cannot_update(self, api: AsyncClient, factory: Factory) -> None:
        """Чужой профиль менять нельзя."""
        user = await factory.user()
        stranger = await factory.user()

        response = await api.patch(
            f"/api/users/{user.id}", json={"full_name": "Взлом"}, headers=as_user(stranger)
        )

        assert response.status_code == 403

    async def test_organizer_cannot_update_other_profile(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Организатор тоже не меняет чужие профили, это может только администратор."""
        admin = await make_admin(factory)
        organizer = await make_organizer(factory, admin)
        user = await factory.user()

        response = await api.patch(
            f"/api/users/{user.id}", json={"full_name": "Чужое"}, headers=as_user(organizer)
        )

        assert response.status_code == 403

    async def test_admin_updates_any_profile(self, api: AsyncClient, factory: Factory) -> None:
        """Администратор меняет любой профиль."""
        admin = await make_admin(factory)
        user = await factory.user()

        response = await api.patch(
            f"/api/users/{user.id}", json={"full_name": "Исправлено"}, headers=as_user(admin)
        )

        assert response.status_code == 200

    async def test_taken_isu_id_is_conflict(self, api: AsyncClient, factory: Factory) -> None:
        """Нельзя взять номер ИСУ, который занят другим пользователем."""
        await factory.user(isu_id="111111")
        user = await factory.user()

        response = await api.patch(
            f"/api/users/{user.id}", json={"isu_id": "111111"}, headers=as_user(user)
        )

        assert response.status_code == 409


class TestSearch:
    """GET /api/users: список и поиск."""

    async def test_volunteer_cannot_list_users(self, api: AsyncClient, factory: Factory) -> None:
        """Список пользователей недоступен волонтёрам."""
        user = await factory.user()

        response = await api.get("/api/users", headers=as_user(user))

        assert response.status_code == 403

    async def test_organizer_lists_users_with_total(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Организатор получает страницу пользователей и общее количество."""
        admin = await make_admin(factory)
        organizer = await make_organizer(factory, admin)
        await factory.user()

        response = await api.get("/api/users?limit=2", headers=as_user(organizer))

        body = response.json()
        assert body["total"] == 3
        assert len(body["items"]) == 2
        assert body["limit"] == 2
        assert body["offset"] == 0

    async def test_pagination_offset(self, api: AsyncClient, factory: Factory) -> None:
        """Смещение пропускает уже показанные записи."""
        admin = await make_admin(factory)
        await factory.user()
        await factory.user()

        first = await api.get("/api/users?limit=2&offset=0", headers=as_user(admin))
        second = await api.get("/api/users?limit=2&offset=2", headers=as_user(admin))

        first_ids = {item["id"] for item in first.json()["items"]}
        second_ids = {item["id"] for item in second.json()["items"]}
        assert first_ids.isdisjoint(second_ids)
        assert len(second_ids) == 1

    @pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
    async def test_invalid_pagination_is_rejected(
        self, api: AsyncClient, factory: Factory, query: str
    ) -> None:
        """Размер страницы ограничен, чтобы нельзя было выгрузить всё одним запросом."""
        admin = await make_admin(factory)

        response = await api.get(f"/api/users?{query}", headers=as_user(admin))

        assert response.status_code == 422

    async def test_filter_by_status(self, api: AsyncClient, factory: Factory) -> None:
        """Фильтр по статусу."""
        admin = await make_admin(factory)
        blocked = await factory.user(status=UserStatus.BLOCKED, comment="Нарушение")

        response = await api.get("/api/users?status=blocked", headers=as_user(admin))

        assert [item["id"] for item in response.json()["items"]] == [blocked.id]

    async def test_filter_by_role(self, api: AsyncClient, factory: Factory) -> None:
        """Фильтр по роли."""
        admin = await make_admin(factory)
        organizer = await make_organizer(factory, admin)
        await factory.user()

        response = await api.get("/api/users?role=organizer", headers=as_user(admin))

        assert [item["id"] for item in response.json()["items"]] == [organizer.id]

    async def test_filter_by_name_ignores_case(self, api: AsyncClient, factory: Factory) -> None:
        """Поиск по ФИО находит часть имени без учёта регистра."""
        admin = await make_admin(factory)
        found = await factory.user(full_name="Иванов Иван Иванович")
        await factory.user(full_name="Петров Пётр")

        response = await api.get(
            "/api/users", params={"full_name": "иВАНОВ"}, headers=as_user(admin)
        )

        assert [item["id"] for item in response.json()["items"]] == [found.id]

    async def test_filter_by_phone(self, api: AsyncClient, factory: Factory) -> None:
        """Поиск по части номера телефона."""
        admin = await make_admin(factory)
        found = await factory.user(phone="+79995554433")
        await factory.user(phone="+79990001122")

        response = await api.get("/api/users", params={"phone": "5554"}, headers=as_user(admin))

        assert [item["id"] for item in response.json()["items"]] == [found.id]

    async def test_wildcards_in_search_are_not_special(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Символ % в поиске ищется буквально и не превращается в «любой текст»."""
        admin = await make_admin(factory)
        await factory.user(full_name="Иванов")

        response = await api.get("/api/users", params={"full_name": "%"}, headers=as_user(admin))

        assert response.json()["total"] == 0

    async def test_deleted_users_are_not_listed(self, api: AsyncClient, factory: Factory) -> None:
        """Мягко удалённые пользователи в списке не показываются."""
        admin = await make_admin(factory)
        user = await factory.user()
        await api.delete(f"/api/users/{user.id}", headers=as_user(admin))

        response = await api.get("/api/users", headers=as_user(admin))

        assert user.id not in {item["id"] for item in response.json()["items"]}

    async def test_items_include_roles(self, api: AsyncClient, factory: Factory) -> None:
        """В списке видны роли пользователей."""
        admin = await make_admin(factory)

        response = await api.get("/api/users", headers=as_user(admin))

        assert response.json()["items"][0]["roles"] == ["admin"]


class TestBlocking:
    """POST /api/users/{id}/block и /unblock."""

    async def test_organizer_blocks_volunteer(self, api: AsyncClient, factory: Factory) -> None:
        """Организатор блокирует волонтёра с указанием причины."""
        admin = await make_admin(factory)
        organizer = await make_organizer(factory, admin)
        user = await factory.user()

        response = await api.post(
            f"/api/users/{user.id}/block",
            json={"comment": "Не пришёл дважды"},
            headers=as_user(organizer),
        )

        body = response.json()
        assert response.status_code == 200
        assert body["status"] == "blocked"
        assert body["comment"] == "Не пришёл дважды"

    async def test_comment_is_required(self, api: AsyncClient, factory: Factory) -> None:
        """Заблокировать без причины нельзя."""
        admin = await make_admin(factory)
        user = await factory.user()

        response = await api.post(
            f"/api/users/{user.id}/block", json={"comment": "  "}, headers=as_user(admin)
        )

        assert response.status_code == 422

    async def test_volunteer_cannot_block(self, api: AsyncClient, factory: Factory) -> None:
        """Волонтёр блокировать не может."""
        volunteer = await factory.user()
        user = await factory.user()

        response = await api.post(
            f"/api/users/{user.id}/block", json={"comment": "x"}, headers=as_user(volunteer)
        )

        assert response.status_code == 403

    async def test_cannot_block_yourself(self, api: AsyncClient, factory: Factory) -> None:
        """Заблокировать самого себя нельзя."""
        admin = await make_admin(factory)

        response = await api.post(
            f"/api/users/{admin.id}/block", json={"comment": "x"}, headers=as_user(admin)
        )

        assert response.status_code == 403

    async def test_organizer_cannot_block_admin(self, api: AsyncClient, factory: Factory) -> None:
        """Организатор не может заблокировать администратора."""
        admin = await make_admin(factory)
        organizer = await make_organizer(factory, admin)

        response = await api.post(
            f"/api/users/{admin.id}/block", json={"comment": "x"}, headers=as_user(organizer)
        )

        assert response.status_code == 403

    async def test_blocked_user_loses_access(self, api: AsyncClient, factory: Factory) -> None:
        """После блокировки пользователь не может выполнять действия."""
        admin = await make_admin(factory)
        user = await factory.user()
        await api.post(
            f"/api/users/{user.id}/block", json={"comment": "Нарушение"}, headers=as_user(admin)
        )

        response = await api.get(f"/api/users/{user.id}", headers=as_user(user))

        assert response.status_code == 403

    async def test_unblock_restores_access(self, api: AsyncClient, factory: Factory) -> None:
        """Разблокировка возвращает статус active."""
        admin = await make_admin(factory)
        user = await factory.user(status=UserStatus.BLOCKED, comment="Нарушение")

        response = await api.post(f"/api/users/{user.id}/unblock", json={}, headers=as_user(admin))

        body = response.json()
        assert body["status"] == "active"
        assert body["comment"] is None

    async def test_unblock_can_keep_a_note(self, api: AsyncClient, factory: Factory) -> None:
        """При разблокировке можно оставить комментарий."""
        admin = await make_admin(factory)
        user = await factory.user(status=UserStatus.BLOCKED, comment="Нарушение")

        response = await api.post(
            f"/api/users/{user.id}/unblock",
            json={"comment": "Разобрались"},
            headers=as_user(admin),
        )

        assert response.json()["comment"] == "Разобрались"

    async def test_unknown_user_is_not_found(self, api: AsyncClient, factory: Factory) -> None:
        """Блокировка несуществующего пользователя — 404."""
        admin = await make_admin(factory)

        response = await api.post(
            "/api/users/999999/block", json={"comment": "x"}, headers=as_user(admin)
        )

        assert response.status_code == 404


class TestDeletion:
    """DELETE /api/users/{id}: мягкое удаление."""

    async def test_user_deletes_himself(self, api: AsyncClient, factory: Factory) -> None:
        """Пользователь может удалить свой аккаунт."""
        user = await factory.user()

        response = await api.delete(f"/api/users/{user.id}", headers=as_user(user))

        assert response.status_code == 204
        assert user.deleted_at is not None

    async def test_admin_deletes_user(self, api: AsyncClient, factory: Factory) -> None:
        """Администратор удаляет любого пользователя."""
        admin = await make_admin(factory)
        user = await factory.user()

        response = await api.delete(f"/api/users/{user.id}", headers=as_user(admin))

        assert response.status_code == 204

    async def test_other_user_cannot_delete(self, api: AsyncClient, factory: Factory) -> None:
        """Чужой аккаунт удалить нельзя."""
        user = await factory.user()
        stranger = await factory.user()

        response = await api.delete(f"/api/users/{user.id}", headers=as_user(stranger))

        assert response.status_code == 403

    async def test_organizer_cannot_delete(self, api: AsyncClient, factory: Factory) -> None:
        """Организатор чужие аккаунты не удаляет."""
        admin = await make_admin(factory)
        organizer = await make_organizer(factory, admin)
        user = await factory.user()

        response = await api.delete(f"/api/users/{user.id}", headers=as_user(organizer))

        assert response.status_code == 403


class TestRoles:
    """Роли: GET/PUT/DELETE /api/users/{id}/roles."""

    async def test_admin_grants_organizer(self, api: AsyncClient, factory: Factory) -> None:
        """Администратор выдаёт организаторские права."""
        admin = await make_admin(factory)
        user = await factory.user()

        response = await api.put(f"/api/users/{user.id}/roles/organizer", headers=as_user(admin))

        assert response.status_code == 200
        assert response.json() == ["organizer"]

    async def test_granting_is_repeatable(self, api: AsyncClient, factory: Factory) -> None:
        """Повторная выдача той же роли ничего не ломает."""
        admin = await make_admin(factory)
        user = await factory.user()
        await api.put(f"/api/users/{user.id}/roles/organizer", headers=as_user(admin))

        response = await api.put(f"/api/users/{user.id}/roles/organizer", headers=as_user(admin))

        assert response.json() == ["organizer"]

    async def test_organizer_cannot_grant_roles(self, api: AsyncClient, factory: Factory) -> None:
        """Организатор не может выдавать организаторские права."""
        admin = await make_admin(factory)
        organizer = await make_organizer(factory, admin)
        user = await factory.user()

        response = await api.put(
            f"/api/users/{user.id}/roles/organizer", headers=as_user(organizer)
        )

        assert response.status_code == 403

    async def test_volunteer_cannot_make_himself_organizer(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Волонтёр не может выдать роль самому себе."""
        await make_admin(factory)
        user = await factory.user()

        response = await api.put(f"/api/users/{user.id}/roles/organizer", headers=as_user(user))

        assert response.status_code == 403

    async def test_user_cannot_make_himself_admin_when_there_are_no_admins(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Даже если администраторов нет, самоназначение невозможно: первого создают в БД."""
        user = await factory.user()

        response = await api.put(f"/api/users/{user.id}/roles/admin", headers=as_user(user))

        assert response.status_code == 403

    async def test_user_sees_own_roles(self, api: AsyncClient, factory: Factory) -> None:
        """Пользователь видит свои роли."""
        admin = await make_admin(factory)

        response = await api.get(f"/api/users/{admin.id}/roles", headers=as_user(admin))

        assert response.json() == ["admin"]

    async def test_volunteer_cannot_see_other_roles(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Роли других видят только организаторы и администраторы."""
        admin = await make_admin(factory)
        volunteer = await factory.user()

        response = await api.get(f"/api/users/{admin.id}/roles", headers=as_user(volunteer))

        assert response.status_code == 403

    async def test_admin_revokes_role(self, api: AsyncClient, factory: Factory) -> None:
        """Администратор снимает роль."""
        admin = await make_admin(factory)
        organizer = await make_organizer(factory, admin)

        response = await api.delete(
            f"/api/users/{organizer.id}/roles/organizer", headers=as_user(admin)
        )

        assert response.json() == []

    async def test_organizer_cannot_revoke(self, api: AsyncClient, factory: Factory) -> None:
        """Организатор роли не снимает."""
        admin = await make_admin(factory)
        organizer = await make_organizer(factory, admin)

        response = await api.delete(
            f"/api/users/{admin.id}/roles/admin", headers=as_user(organizer)
        )

        assert response.status_code == 403

    async def test_last_admin_cannot_be_removed(self, api: AsyncClient, factory: Factory) -> None:
        """Нельзя снять роль с последнего администратора."""
        admin = await make_admin(factory)

        response = await api.delete(f"/api/users/{admin.id}/roles/admin", headers=as_user(admin))

        assert response.status_code == 409

    async def test_unknown_role_is_rejected(self, api: AsyncClient, factory: Factory) -> None:
        """Несуществующая роль отклоняется."""
        admin = await make_admin(factory)

        response = await api.put(f"/api/users/{admin.id}/roles/boss", headers=as_user(admin))

        assert response.status_code == 422

    async def test_new_organizer_gets_staff_rights(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """После выдачи роли организатора пользователь видит список пользователей."""
        admin = await make_admin(factory)
        user = await factory.user()
        await api.put(f"/api/users/{user.id}/roles/organizer", headers=as_user(admin))

        response = await api.get("/api/users", headers=as_user(user))

        assert response.status_code == 200
