from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.database.models import User
from app.database.models.enums import (
    BroadcastStatus,
    NotificationType,
    RegistrationStatus,
    RoleType,
    UserStatus,
)
from tests.app.api.support import as_user, make_admin, make_organizer
from tests.app.conftest import FakePublisher
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


class TestBroadcastSending:
    """Отправка уже сохранённого черновика."""

    async def test_subscribers_receive_the_text_and_others_do_not(
        self, api: AsyncClient, factory: Factory, published: FakePublisher
    ) -> None:
        """Подписчикам уходит текст, отключившим уведомления и заблокированным — нет."""
        admin = await make_admin(factory)
        subscriber = await factory.user()
        await factory.user(has_notifications_enabled=False)
        await factory.user(status=UserStatus.BLOCKED, comment="нарушения")
        created = await api.post(
            "/api/broadcasts",
            json={"text": "Анонс недели", "audience": "announcements_subscribers"},
            headers=as_user(admin),
        )

        sent = await api.post(
            f"/api/broadcasts/{created.json()['id']}/send", headers=as_user(admin)
        )

        assert sent.status_code == 200
        assert sent.json()["status"] == BroadcastStatus.SENT
        assert {message.telegram_id for message in published.messages} == {
            admin.telegram_id,
            subscriber.telegram_id,
        }
        assert published.messages[0].type is NotificationType.BROADCAST
        assert published.messages[0].payload == {"text": "Анонс недели"}

    async def test_all_includes_people_who_turned_notifications_off(
        self, api: AsyncClient, factory: Factory, published: FakePublisher
    ) -> None:
        """Аудитория «все» включает тех, кто отключил необязательные уведомления."""
        admin = await make_admin(factory)
        quiet = await factory.user(has_notifications_enabled=False)
        created = await api.post(
            "/api/broadcasts",
            json={"text": "Важное", "audience": "all"},
            headers=as_user(admin),
        )

        await api.post(f"/api/broadcasts/{created.json()['id']}/send", headers=as_user(admin))

        assert quiet.telegram_id in {message.telegram_id for message in published.messages}

    async def test_event_participants_and_a_second_send_is_rejected(
        self, api: AsyncClient, factory: Factory, published: FakePublisher
    ) -> None:
        """Участникам мероприятия уходит текст, повторная отправка отклоняется."""
        admin = await make_admin(factory)
        organizer = await make_organizer(factory, admin)
        event = await factory.event(organizer=organizer)
        participant = await factory.user()
        await factory.registration(event, participant, status=RegistrationStatus.REGISTERED)
        await factory.registration(
            event,
            await factory.user(),
            status=RegistrationStatus.CANCELLED,
            cancelled_at=datetime.now(UTC),
            cancellation_reason="не смогу",
        )
        created = await api.post(
            "/api/broadcasts",
            json={
                "text": "Сбор у метро",
                "audience": "event_participants",
                "event_id": event.id,
            },
            headers=as_user(organizer),
        )

        first = await api.post(
            f"/api/broadcasts/{created.json()['id']}/send", headers=as_user(organizer)
        )
        second = await api.post(
            f"/api/broadcasts/{created.json()['id']}/send", headers=as_user(organizer)
        )

        assert first.status_code == 200
        assert second.status_code == 409
        (message,) = published.messages
        assert message.telegram_id == participant.telegram_id
