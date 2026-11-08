import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Bonus, Tag
from app.database.models.enums import UserStatus
from tests.app.api.support import as_user, make_admin, make_organizer
from tests.app.database.factory import Factory

pytestmark = pytest.mark.integration

Titled = type[Bonus] | type[Tag]

RESOURCES = pytest.mark.parametrize(
    ("path", "model"), [("/api/bonuses", Bonus), ("/api/tags", Tag)], ids=["bonuses", "tags"]
)
PATHS = pytest.mark.parametrize("path", ["/api/bonuses", "/api/tags"], ids=["bonuses", "tags"])


class TestTitleList:
    """Список бонусов и тегов."""

    @RESOURCES
    async def test_volunteer_sees_items_in_alphabetical_order(
        self, api: AsyncClient, factory: Factory, session: AsyncSession, path: str, model: Titled
    ) -> None:
        """Список по алфавиту без учёта регистра доступен обычному волонтёру."""
        session.add_all([model(title="яблоко"), model(title="Арбуз"), model(title="бананы")])
        volunteer = await factory.user()
        await session.flush()

        response = await api.get(path, headers=as_user(volunteer))

        assert [item["title"] for item in response.json()] == ["Арбуз", "бананы", "яблоко"]

    @RESOURCES
    async def test_item_has_id_title_and_creation_time(
        self, api: AsyncClient, factory: Factory, session: AsyncSession, path: str, model: Titled
    ) -> None:
        """В записи есть идентификатор, название и время добавления."""
        session.add(model(title="Один"))
        volunteer = await factory.user()
        await session.flush()

        response = await api.get(path, headers=as_user(volunteer))

        assert set(response.json()[0]) == {"id", "title", "created_at"}

    @PATHS
    async def test_deleted_items_are_hidden(
        self, api: AsyncClient, factory: Factory, path: str
    ) -> None:
        """Удалённые записи в списке не показываются."""
        admin = await make_admin(factory)
        created = await api.post(path, json={"title": "Лишнее"}, headers=as_user(admin))
        await api.delete(f"{path}/{created.json()['id']}", headers=as_user(admin))

        response = await api.get(path, headers=as_user(admin))

        assert response.json() == []

    @PATHS
    async def test_unregistered_user_is_unauthorized(self, api: AsyncClient, path: str) -> None:
        """Без заголовка X-Telegram-Id список недоступен."""
        response = await api.get(path)

        assert response.status_code == 401

    @PATHS
    async def test_blocked_user_is_forbidden(
        self, api: AsyncClient, factory: Factory, path: str
    ) -> None:
        """Заблокированному пользователю список недоступен."""
        user = await factory.user(status=UserStatus.BLOCKED, comment="Нарушение")

        response = await api.get(path, headers=as_user(user))

        assert response.status_code == 403

    @PATHS
    async def test_service_token_is_required(self, api: AsyncClient, path: str) -> None:
        """Без токена бота список недоступен."""
        response = await api.get(path, headers={"Authorization": ""})

        assert response.status_code == 401


class TestTitleCreate:
    """Добавление бонусов и тегов."""

    @RESOURCES
    async def test_organizer_adds_item(
        self,
        api: AsyncClient,
        factory: Factory,
        session: AsyncSession,
        path: str,
        model: Titled,
    ) -> None:
        """Организатор добавляет запись, и в ней запоминается автор."""
        organizer = await make_organizer(factory, await make_admin(factory))

        response = await api.post(path, json={"title": "Новый"}, headers=as_user(organizer))

        assert response.status_code == 201
        assert response.json()["title"] == "Новый"
        stored = await session.get(model, response.json()["id"])
        assert isinstance(stored, model)
        assert stored.created_by == organizer.id

    @PATHS
    async def test_volunteer_cannot_add(
        self, api: AsyncClient, factory: Factory, path: str
    ) -> None:
        """Волонтёр не может добавлять записи."""
        volunteer = await factory.user()

        response = await api.post(path, json={"title": "Новый"}, headers=as_user(volunteer))

        assert response.status_code == 403

    @PATHS
    async def test_duplicate_ignores_case(
        self, api: AsyncClient, factory: Factory, path: str
    ) -> None:
        """Название уникально без учёта регистра."""
        admin = await make_admin(factory)
        await api.post(path, json={"title": "Собаки"}, headers=as_user(admin))

        response = await api.post(path, json={"title": "собаки"}, headers=as_user(admin))

        assert response.status_code == 409
        assert response.json()["code"] == "conflict"

    @PATHS
    async def test_title_is_available_again_after_deletion(
        self, api: AsyncClient, factory: Factory, path: str
    ) -> None:
        """После удаления то же название можно добавить снова."""
        admin = await make_admin(factory)
        created = await api.post(path, json={"title": "Собаки"}, headers=as_user(admin))
        await api.delete(f"{path}/{created.json()['id']}", headers=as_user(admin))

        response = await api.post(path, json={"title": "Собаки"}, headers=as_user(admin))

        assert response.status_code == 201

    @PATHS
    async def test_title_is_trimmed(self, api: AsyncClient, factory: Factory, path: str) -> None:
        """Пробелы по краям названия отбрасываются."""
        admin = await make_admin(factory)

        response = await api.post(path, json={"title": "  Кошки  "}, headers=as_user(admin))

        assert response.json()["title"] == "Кошки"

    @PATHS
    @pytest.mark.parametrize("title", ["", "   ", "я" * 256])
    async def test_invalid_title_is_rejected(
        self, api: AsyncClient, factory: Factory, path: str, title: str
    ) -> None:
        """Пустое и слишком длинное название отклоняются."""
        admin = await make_admin(factory)

        response = await api.post(path, json={"title": title}, headers=as_user(admin))

        assert response.status_code == 422

    @PATHS
    async def test_unknown_field_is_rejected(
        self, api: AsyncClient, factory: Factory, path: str
    ) -> None:
        """Лишние поля в запросе отклоняются."""
        admin = await make_admin(factory)

        response = await api.post(
            path, json={"title": "Новый", "created_by": 1}, headers=as_user(admin)
        )

        assert response.status_code == 422

    @pytest.mark.parametrize(
        ("sent", "stored"), [("#Выезд", "Выезд"), ("  # Выезд ", "Выезд"), ("##Выезд", "#Выезд")]
    )
    async def test_tag_loses_leading_hash(
        self, api: AsyncClient, factory: Factory, sent: str, stored: str
    ) -> None:
        """Теги хранятся без ведущего #, чтобы #Выезд и Выезд не дублировались."""
        admin = await make_admin(factory)

        response = await api.post("/api/tags", json={"title": sent}, headers=as_user(admin))

        assert response.json()["title"] == stored

    @pytest.mark.parametrize("title", ["#", " # "])
    async def test_tag_cannot_be_only_hash(
        self, api: AsyncClient, factory: Factory, title: str
    ) -> None:
        """Тег из одного # отклоняется."""
        admin = await make_admin(factory)

        response = await api.post("/api/tags", json={"title": title}, headers=as_user(admin))

        assert response.status_code == 422

    async def test_bonus_keeps_hash(self, api: AsyncClient, factory: Factory) -> None:
        """У бонусов # не отбрасывается: это правило только для тегов."""
        admin = await make_admin(factory)

        response = await api.post("/api/bonuses", json={"title": "#1"}, headers=as_user(admin))

        assert response.json()["title"] == "#1"


class TestTitleDelete:
    """Удаление бонусов и тегов."""

    @RESOURCES
    async def test_organizer_deletes_item_softly(
        self,
        api: AsyncClient,
        factory: Factory,
        session: AsyncSession,
        path: str,
        model: Titled,
    ) -> None:
        """Запись помечается удалённой, но остаётся в БД."""
        admin = await make_admin(factory)
        organizer = await make_organizer(factory, admin)
        created = await api.post(path, json={"title": "Лишнее"}, headers=as_user(admin))
        item_id = created.json()["id"]

        response = await api.delete(f"{path}/{item_id}", headers=as_user(organizer))

        assert response.status_code == 204
        stored = await session.get(model, item_id)
        assert isinstance(stored, model)
        assert stored.deleted_at is not None

    @PATHS
    async def test_volunteer_cannot_delete(
        self, api: AsyncClient, factory: Factory, path: str
    ) -> None:
        """Волонтёр не может удалять записи."""
        admin = await make_admin(factory)
        created = await api.post(path, json={"title": "Лишнее"}, headers=as_user(admin))
        volunteer = await factory.user()

        response = await api.delete(f"{path}/{created.json()['id']}", headers=as_user(volunteer))

        assert response.status_code == 403

    @PATHS
    async def test_unknown_item_is_not_found(
        self, api: AsyncClient, factory: Factory, path: str
    ) -> None:
        """Несуществующая запись — 404."""
        admin = await make_admin(factory)

        response = await api.delete(f"{path}/999999", headers=as_user(admin))

        assert response.status_code == 404

    @PATHS
    async def test_deleting_twice_is_not_found(
        self, api: AsyncClient, factory: Factory, path: str
    ) -> None:
        """Повторное удаление — 404."""
        admin = await make_admin(factory)
        created = await api.post(path, json={"title": "Лишнее"}, headers=as_user(admin))
        url = f"{path}/{created.json()['id']}"
        await api.delete(url, headers=as_user(admin))

        response = await api.delete(url, headers=as_user(admin))

        assert response.status_code == 404
