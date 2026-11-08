from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Shelter
from app.database.models.enums import UserStatus
from tests.app.api.support import as_user, make_admin, make_organizer
from tests.app.database.factory import Factory

pytestmark = pytest.mark.integration

NEW_SHELTER: dict[str, Any] = {
    "title": "Приют «Добрые руки»",
    "address": "Санкт-Петербург, ул. Лесная, 1",
    "instructions": "Сменная обувь",
    "is_approval_required": True,
    "contacts": [
        {"type": "phone", "value": "+78125550000"},
        {"type": "website", "value": "https://example.org"},
    ],
}


class TestShelterRead:
    """Просмотр приютов."""

    async def test_volunteer_sees_shelters_in_alphabetical_order(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Список по алфавиту без учёта регистра доступен обычному волонтёру."""
        await factory.shelter(title="яблоня")
        await factory.shelter(title="Берёзка")
        volunteer = await factory.user()

        response = await api.get("/api/shelters", headers=as_user(volunteer))

        assert [item["title"] for item in response.json()] == ["Берёзка", "яблоня"]

    async def test_shelter_has_all_fields_and_contacts(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """В карточке приюта есть поля и контакты."""
        admin = await make_admin(factory)
        created = await api.post("/api/shelters", json=NEW_SHELTER, headers=as_user(admin))

        response = await api.get(f"/api/shelters/{created.json()['id']}", headers=as_user(admin))

        body = response.json()
        assert body["title"] == NEW_SHELTER["title"]
        assert body["address"] == NEW_SHELTER["address"]
        assert body["instructions"] == "Сменная обувь"
        assert body["is_approval_required"] is True
        assert {(c["type"], c["value"]) for c in body["contacts"]} == {
            ("phone", "+78125550000"),
            ("website", "https://example.org"),
        }
        assert set(body) == {
            "id",
            "title",
            "address",
            "instructions",
            "is_approval_required",
            "contacts",
            "created_at",
        }

    async def test_unknown_shelter_is_not_found(self, api: AsyncClient, factory: Factory) -> None:
        """Несуществующий приют — 404."""
        volunteer = await factory.user()

        response = await api.get("/api/shelters/999999", headers=as_user(volunteer))

        assert response.status_code == 404

    async def test_deleted_shelter_is_hidden(
        self, api: AsyncClient, factory: Factory, session: AsyncSession
    ) -> None:
        """Удалённый приют не показывается ни в списке, ни по ID."""
        admin = await make_admin(factory)
        shelter = await factory.shelter()
        await api.delete(f"/api/shelters/{shelter.id}", headers=as_user(admin))

        listing = await api.get("/api/shelters", headers=as_user(admin))
        card = await api.get(f"/api/shelters/{shelter.id}", headers=as_user(admin))

        assert listing.json() == []
        assert card.status_code == 404

    async def test_blocked_user_is_forbidden(self, api: AsyncClient, factory: Factory) -> None:
        """Заблокированному пользователю приюты недоступны."""
        user = await factory.user(status=UserStatus.BLOCKED, comment="Нарушение")

        response = await api.get("/api/shelters", headers=as_user(user))

        assert response.status_code == 403

    async def test_service_token_is_required(self, api: AsyncClient) -> None:
        """Без токена бота приюты недоступны."""
        response = await api.get("/api/shelters", headers={"Authorization": ""})

        assert response.status_code == 401


class TestShelterCreate:
    """Добавление приютов."""

    async def test_organizer_creates_shelter_with_contacts(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Организатор добавляет приют сразу с контактами."""
        organizer = await make_organizer(factory, await make_admin(factory))

        response = await api.post("/api/shelters", json=NEW_SHELTER, headers=as_user(organizer))

        assert response.status_code == 201
        assert len(response.json()["contacts"]) == 2

    async def test_defaults(self, api: AsyncClient, factory: Factory) -> None:
        """Без необязательных полей приют создаётся без требований, контактов и одобрения."""
        admin = await make_admin(factory)
        payload = {"title": "Лапы", "address": "Адрес"}

        response = await api.post("/api/shelters", json=payload, headers=as_user(admin))

        body = response.json()
        assert body["instructions"] is None
        assert body["is_approval_required"] is False
        assert body["contacts"] == []

    async def test_volunteer_cannot_create(self, api: AsyncClient, factory: Factory) -> None:
        """Волонтёр не может добавлять приюты."""
        volunteer = await factory.user()

        response = await api.post("/api/shelters", json=NEW_SHELTER, headers=as_user(volunteer))

        assert response.status_code == 403

    @pytest.mark.parametrize(
        "payload",
        [
            {"title": "", "address": "Адрес"},
            {"title": "Приют", "address": "   "},
            {"title": "я" * 256, "address": "Адрес"},
            {"title": "Приют", "address": "я" * 501},
            {"title": "Приют", "address": "Адрес", "instructions": ""},
            {"title": "Приют", "address": "Адрес", "extra": 1},
            {"title": "Приют", "address": "Адрес", "contacts": [{"type": "fax", "value": "1"}]},
            {"title": "Приют", "address": "Адрес", "contacts": [{"type": "phone", "value": " "}]},
            {
                "title": "Приют",
                "address": "Адрес",
                "contacts": [{"type": "phone", "value": "1"}, {"type": "phone", "value": "1"}],
            },
            {
                "title": "Приют",
                "address": "Адрес",
                "contacts": [{"type": "phone", "value": str(n)} for n in range(21)],
            },
        ],
    )
    async def test_invalid_payload_is_rejected(
        self, api: AsyncClient, factory: Factory, payload: dict[str, Any]
    ) -> None:
        """Некорректные данные отклоняются."""
        admin = await make_admin(factory)

        response = await api.post("/api/shelters", json=payload, headers=as_user(admin))

        assert response.status_code == 422

    async def test_same_value_with_different_type_is_allowed(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Одинаковое значение разрешено, если тип контакта разный."""
        admin = await make_admin(factory)
        payload = {
            "title": "Приют",
            "address": "Адрес",
            "contacts": [{"type": "vk", "value": "x"}, {"type": "telegram", "value": "x"}],
        }

        response = await api.post("/api/shelters", json=payload, headers=as_user(admin))

        assert response.status_code == 201


class TestShelterUpdate:
    """Изменение приютов."""

    async def test_organizer_updates_only_sent_fields(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Меняются только переданные поля."""
        organizer = await make_organizer(factory, await make_admin(factory))
        shelter = await factory.shelter(title="Старое", address="Адрес", instructions="Правила")

        response = await api.patch(
            f"/api/shelters/{shelter.id}", json={"title": "Новое"}, headers=as_user(organizer)
        )

        body = response.json()
        assert body["title"] == "Новое"
        assert body["address"] == "Адрес"
        assert body["instructions"] == "Правила"

    async def test_instructions_can_be_cleared(self, api: AsyncClient, factory: Factory) -> None:
        """Требования можно очистить значением null."""
        admin = await make_admin(factory)
        shelter = await factory.shelter(instructions="Правила")

        response = await api.patch(
            f"/api/shelters/{shelter.id}", json={"instructions": None}, headers=as_user(admin)
        )

        assert response.json()["instructions"] is None

    @pytest.mark.parametrize("field", ["title", "address", "is_approval_required"])
    async def test_required_fields_cannot_be_cleared(
        self, api: AsyncClient, factory: Factory, field: str
    ) -> None:
        """Обязательные поля нельзя очистить."""
        admin = await make_admin(factory)
        shelter = await factory.shelter()

        response = await api.patch(
            f"/api/shelters/{shelter.id}", json={field: None}, headers=as_user(admin)
        )

        assert response.status_code == 422

    async def test_contacts_are_not_changed_here(self, api: AsyncClient, factory: Factory) -> None:
        """Контакты меняются отдельными запросами, а не через изменение приюта."""
        admin = await make_admin(factory)
        shelter = await factory.shelter()

        response = await api.patch(
            f"/api/shelters/{shelter.id}", json={"contacts": []}, headers=as_user(admin)
        )

        assert response.status_code == 422

    async def test_volunteer_cannot_update(self, api: AsyncClient, factory: Factory) -> None:
        """Волонтёр не может менять приют."""
        volunteer = await factory.user()
        shelter = await factory.shelter()

        response = await api.patch(
            f"/api/shelters/{shelter.id}", json={"title": "X"}, headers=as_user(volunteer)
        )

        assert response.status_code == 403

    async def test_unknown_shelter_is_not_found(self, api: AsyncClient, factory: Factory) -> None:
        """Несуществующий приют — 404."""
        admin = await make_admin(factory)

        response = await api.patch(
            "/api/shelters/999999", json={"title": "X"}, headers=as_user(admin)
        )

        assert response.status_code == 404


class TestShelterDelete:
    """Удаление приютов."""

    async def test_admin_deletes_shelter_softly(
        self, api: AsyncClient, factory: Factory, session: AsyncSession
    ) -> None:
        """Администратор удаляет приют мягко: запись остаётся в БД."""
        admin = await make_admin(factory)
        shelter = await factory.shelter()

        response = await api.delete(f"/api/shelters/{shelter.id}", headers=as_user(admin))

        assert response.status_code == 204
        stored = await session.get(Shelter, shelter.id)
        assert stored is not None
        assert stored.deleted_at is not None

    async def test_organizer_cannot_delete(self, api: AsyncClient, factory: Factory) -> None:
        """Удалять приюты может только администратор."""
        organizer = await make_organizer(factory, await make_admin(factory))
        shelter = await factory.shelter()

        response = await api.delete(f"/api/shelters/{shelter.id}", headers=as_user(organizer))

        assert response.status_code == 403

    async def test_unknown_shelter_is_not_found(self, api: AsyncClient, factory: Factory) -> None:
        """Несуществующий приют — 404."""
        admin = await make_admin(factory)

        response = await api.delete("/api/shelters/999999", headers=as_user(admin))

        assert response.status_code == 404


class TestShelterContacts:
    """Контакты приюта."""

    async def test_organizer_adds_contact(self, api: AsyncClient, factory: Factory) -> None:
        """Организатор добавляет контакт, и он появляется в карточке."""
        organizer = await make_organizer(factory, await make_admin(factory))
        shelter = await factory.shelter()

        response = await api.post(
            f"/api/shelters/{shelter.id}/contacts",
            json={"type": "email", "value": " info@example.org "},
            headers=as_user(organizer),
        )

        assert response.status_code == 201
        assert response.json()["value"] == "info@example.org"
        card = await api.get(f"/api/shelters/{shelter.id}", headers=as_user(organizer))
        assert [c["type"] for c in card.json()["contacts"]] == ["email"]

    async def test_duplicate_contact_is_conflict(self, api: AsyncClient, factory: Factory) -> None:
        """Тот же тип и значение второй раз — 409."""
        admin = await make_admin(factory)
        shelter = await factory.shelter()
        payload = {"type": "phone", "value": "+78125550000"}
        await api.post(f"/api/shelters/{shelter.id}/contacts", json=payload, headers=as_user(admin))

        response = await api.post(
            f"/api/shelters/{shelter.id}/contacts", json=payload, headers=as_user(admin)
        )

        assert response.status_code == 409

    async def test_volunteer_cannot_add_contact(self, api: AsyncClient, factory: Factory) -> None:
        """Волонтёр не может добавлять контакты."""
        volunteer = await factory.user()
        shelter = await factory.shelter()

        response = await api.post(
            f"/api/shelters/{shelter.id}/contacts",
            json={"type": "phone", "value": "1"},
            headers=as_user(volunteer),
        )

        assert response.status_code == 403

    async def test_contact_of_unknown_shelter_is_not_found(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Контакт нельзя добавить несуществующему приюту."""
        admin = await make_admin(factory)

        response = await api.post(
            "/api/shelters/999999/contacts",
            json={"type": "phone", "value": "1"},
            headers=as_user(admin),
        )

        assert response.status_code == 404

    async def test_organizer_deletes_contact(self, api: AsyncClient, factory: Factory) -> None:
        """Организатор удаляет контакт."""
        admin = await make_admin(factory)
        created = await api.post("/api/shelters", json=NEW_SHELTER, headers=as_user(admin))
        shelter_id = created.json()["id"]
        contact_id = created.json()["contacts"][0]["id"]

        response = await api.delete(
            f"/api/shelters/{shelter_id}/contacts/{contact_id}", headers=as_user(admin)
        )

        assert response.status_code == 204
        card = await api.get(f"/api/shelters/{shelter_id}", headers=as_user(admin))
        assert len(card.json()["contacts"]) == 1

    async def test_volunteer_cannot_delete_contact(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Волонтёр не может удалять контакты."""
        admin = await make_admin(factory)
        volunteer = await factory.user()
        created = await api.post("/api/shelters", json=NEW_SHELTER, headers=as_user(admin))
        contact_id = created.json()["contacts"][0]["id"]

        response = await api.delete(
            f"/api/shelters/{created.json()['id']}/contacts/{contact_id}",
            headers=as_user(volunteer),
        )

        assert response.status_code == 403

    async def test_contact_of_another_shelter_is_not_found(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Контакт другого приюта удалить через этот приют нельзя."""
        admin = await make_admin(factory)
        first = await api.post("/api/shelters", json=NEW_SHELTER, headers=as_user(admin))
        other = await factory.shelter()
        contact_id = first.json()["contacts"][0]["id"]

        response = await api.delete(
            f"/api/shelters/{other.id}/contacts/{contact_id}", headers=as_user(admin)
        )

        assert response.status_code == 404
        card = await api.get(f"/api/shelters/{first.json()['id']}", headers=as_user(admin))
        assert len(card.json()["contacts"]) == 2

    async def test_contact_of_unknown_shelter_cannot_be_deleted(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """У несуществующего приюта контакт удалить нельзя."""
        admin = await make_admin(factory)

        response = await api.delete("/api/shelters/999999/contacts/1", headers=as_user(admin))

        assert response.status_code == 404
