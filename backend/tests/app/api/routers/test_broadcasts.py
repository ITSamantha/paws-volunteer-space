import pytest
from httpx import AsyncClient

from app.database.models import User
from app.database.models.enums import BroadcastStatus, RoleType
from tests.app.api.support import as_user, make_admin, make_organizer
from tests.app.database.factory import Factory

pytestmark = pytest.mark.integration


async def make_smm(factory: Factory, admin: User) -> User:
    smm = await factory.user()

    await factory.role(smm, RoleType.SMM, admin)

    return smm


class TestBroadcastDrafts:
    """Черновики рассылок без отправки."""

    async def test_smm_saves_a_draft(self, api: AsyncClient, factory: Factory) -> None:
        """SMM создаёт черновик для всех, и он никуда не уходит."""
        admin = await make_admin(factory)
        smm = await make_smm(factory, admin)

        response = await api.post(
            "/api/broadcasts",
            json={"text": "В воскресенье выезд", "audience": "all"},
            headers=as_user(smm),
        )

        body = response.json()
        assert response.status_code == 201
        assert body["author_id"] == smm.id
        assert body["status"] == BroadcastStatus.DRAFT
        assert body["sent_at"] is None
        assert body["event_id"] is None

    async def test_volunteer_cannot_create(self, api: AsyncClient, factory: Factory) -> None:
        """Волонтёр не готовит рассылки."""
        volunteer = await factory.user()

        response = await api.post(
            "/api/broadcasts",
            json={"text": "Всем привет", "audience": "all"},
            headers=as_user(volunteer),
        )

        assert response.status_code == 403

    async def test_participants_need_an_existing_event(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Аудитория «участники» требует существующее мероприятие."""
        admin = await make_admin(factory)

        missing = await api.post(
            "/api/broadcasts",
            json={"text": "Напоминание", "audience": "event_participants", "event_id": 1},
            headers=as_user(admin),
        )
        extra = await api.post(
            "/api/broadcasts",
            json={"text": "Всем", "audience": "all", "event_id": 1},
            headers=as_user(admin),
        )

        assert missing.status_code == 422
        assert extra.status_code == 422

    async def test_author_edits_a_draft_and_others_read_it(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Автор правит черновик, организатор видит его в списке и в карточке."""
        admin = await make_admin(factory)
        smm = await make_smm(factory, admin)
        organizer = await make_organizer(factory, admin)
        event = await factory.event(organizer=organizer)
        created = await api.post(
            "/api/broadcasts",
            json={"text": "Черновик", "audience": "all"},
            headers=as_user(smm),
        )

        updated = await api.patch(
            f"/api/broadcasts/{created.json()['id']}",
            json={"audience": "event_participants", "event_id": event.id},
            headers=as_user(smm),
        )
        listed = await api.get("/api/broadcasts", headers=as_user(organizer))
        card = await api.get(f"/api/broadcasts/{created.json()['id']}", headers=as_user(organizer))

        assert updated.status_code == 200
        assert updated.json()["event_id"] == event.id
        assert listed.json()["total"] == 1
        assert card.json()["text"] == "Черновик"

    async def test_another_organizer_cannot_edit_a_foreign_draft(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Чужой черновик правит только администратор."""
        admin = await make_admin(factory)
        smm = await make_smm(factory, admin)
        organizer = await make_organizer(factory, admin)
        created = await api.post(
            "/api/broadcasts",
            json={"text": "Черновик", "audience": "announcements_subscribers"},
            headers=as_user(smm),
        )

        denied = await api.patch(
            f"/api/broadcasts/{created.json()['id']}",
            json={"text": "Чужое"},
            headers=as_user(organizer),
        )
        allowed = await api.patch(
            f"/api/broadcasts/{created.json()['id']}",
            json={"text": "От админа"},
            headers=as_user(admin),
        )

        assert denied.status_code == 403
        assert allowed.json()["text"] == "От админа"
