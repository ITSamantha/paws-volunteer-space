from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient

from app.database.models import Event, User
from app.database.models.enums import NotificationType, RegistrationStatus
from tests.app.api.support import as_user, make_admin, make_organizer
from tests.app.conftest import FakePublisher
from tests.app.database.factory import Factory

pytestmark = pytest.mark.integration


def past() -> datetime:
    return datetime.now(UTC) - timedelta(hours=3)


async def event_of(factory: Factory, **fields: Any) -> tuple[User, Event]:
    admin = await make_admin(factory)
    organizer = await make_organizer(factory, admin)
    event = await factory.event(organizer=organizer, **fields)

    return organizer, event


def url(event: Event, suffix: str = "") -> str:
    return f"/api/events/{event.id}/registrations{suffix}"


def types(notifications: list[Any]) -> list[NotificationType]:
    return [item.type for item in notifications]


async def fill(factory: Factory, event: Event, count: int) -> None:
    for _ in range(count):
        await factory.registration(event, await factory.user())


class TestRegister:
    """Запись на мероприятие."""

    async def test_volunteer_gets_a_place(self, api: AsyncClient, factory: Factory) -> None:
        """При свободных местах запись подтверждается сразу."""
        _, event = await event_of(factory)
        volunteer = await factory.user()

        response = await api.post(url(event), headers=as_user(volunteer))

        assert response.status_code == 201
        assert response.json()["status"] == "registered"
        assert response.json()["event_id"] == event.id

    async def test_place_is_counted(self, api: AsyncClient, factory: Factory) -> None:
        """Занятое место сразу видно в карточке мероприятия."""
        _, event = await event_of(factory, capacity=3)
        volunteer = await factory.user()
        await api.post(url(event), headers=as_user(volunteer))

        response = await api.get(f"/api/events/{event.id}", headers=as_user(volunteer))

        assert response.json()["occupied"] == 1

    async def test_user_and_organizer_are_notified(
        self, api: AsyncClient, factory: Factory, published: FakePublisher
    ) -> None:
        """Волонтёр получает подтверждение, организатор — сообщение о новой записи."""
        organizer, event = await event_of(factory)
        volunteer = await factory.user()

        await api.post(url(event), headers=as_user(volunteer))

        sent = {item.telegram_id: item.type for item in published.messages}
        assert sent == {
            volunteer.telegram_id: NotificationType.REGISTRATION_CONFIRMED,
            organizer.telegram_id: NotificationType.ORGANIZER_NEW_REGISTRATION,
        }

    async def test_approval_makes_registration_pending(
        self, api: AsyncClient, factory: Factory, published: FakePublisher
    ) -> None:
        """Если нужно одобрение, запись ждёт решения организатора."""
        organizer, event = await event_of(factory, is_approval_required=True)
        volunteer = await factory.user()

        response = await api.post(url(event), headers=as_user(volunteer))

        assert response.json()["status"] == "pending"
        sent = {item.telegram_id: item.type for item in published.messages}
        assert sent == {
            volunteer.telegram_id: NotificationType.REGISTRATION_PENDING,
            organizer.telegram_id: NotificationType.ORGANIZER_APPROVAL_REQUESTED,
        }

    async def test_full_event_puts_user_on_waitlist(
        self, api: AsyncClient, factory: Factory, published: FakePublisher
    ) -> None:
        """Когда мест нет, пользователь попадает в лист ожидания, организатору не пишем."""
        _, event = await event_of(factory, capacity=2)
        await fill(factory, event, 2)
        volunteer = await factory.user()

        response = await api.post(url(event), headers=as_user(volunteer))

        assert response.json()["status"] == "waitlisted"
        sent = published.messages
        assert [(n.telegram_id, n.type) for n in sent] == [
            (volunteer.telegram_id, NotificationType.REGISTRATION_WAITLISTED)
        ]

    async def test_full_event_with_approval_still_waitlists(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Заявка без места тоже уходит в лист ожидания."""
        _, event = await event_of(factory, capacity=1, is_approval_required=True)
        await fill(factory, event, 1)
        volunteer = await factory.user()

        response = await api.post(url(event), headers=as_user(volunteer))

        assert response.json()["status"] == "waitlisted"

    async def test_pending_places_are_reserved(self, api: AsyncClient, factory: Factory) -> None:
        """Заявка, ожидающая одобрения, занимает место."""
        _, event = await event_of(factory, capacity=1, is_approval_required=True)
        first, second = await factory.user(), await factory.user()

        await api.post(url(event), headers=as_user(first))
        response = await api.post(url(event), headers=as_user(second))

        assert response.json()["status"] == "waitlisted"

    @pytest.mark.parametrize(
        "status",
        [
            RegistrationStatus.REGISTERED,
            RegistrationStatus.PENDING,
            RegistrationStatus.WAITLISTED,
            RegistrationStatus.ATTENDED,
        ],
    )
    async def test_cannot_register_twice(
        self, api: AsyncClient, factory: Factory, status: RegistrationStatus
    ) -> None:
        """Повторная запись невозможна, пока прежняя действует."""
        _, event = await event_of(factory)
        volunteer = await factory.user()
        await factory.registration(event, volunteer, status=status)

        response = await api.post(url(event), headers=as_user(volunteer))

        assert response.status_code == 409

    async def test_rejected_user_cannot_register_again(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Отклонённая заявка не подаётся повторно."""
        organizer, event = await event_of(factory)
        volunteer = await factory.user()
        await factory.registration(
            event,
            volunteer,
            status=RegistrationStatus.REJECTED,
            decided_by=organizer.id,
            decided_at=datetime.now(UTC),
            decision_comment="Нет",
        )

        response = await api.post(url(event), headers=as_user(volunteer))

        assert response.status_code == 409

    async def test_can_register_again_after_cancellation(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """После отмены можно записаться снова, прежняя отмена сбрасывается."""
        _, event = await event_of(factory)
        volunteer = await factory.user()
        await api.post(url(event), headers=as_user(volunteer))
        await api.post(
            url(event, "/me/cancel"), json={"reason": "Заболел"}, headers=as_user(volunteer)
        )

        response = await api.post(url(event), headers=as_user(volunteer))

        body = response.json()
        assert response.status_code == 201
        assert body["status"] == "registered"
        assert body["cancelled_at"] is None
        assert body["cancellation_reason"] is None

    async def test_organizer_is_not_notified_about_own_registration(
        self, api: AsyncClient, factory: Factory, published: FakePublisher
    ) -> None:
        """Организатор, записавшийся на своё мероприятие, не получает сообщение о себе."""
        organizer, event = await event_of(factory)

        await api.post(url(event), headers=as_user(organizer))

        sent = published.messages
        assert [(n.telegram_id, n.type) for n in sent] == [
            (organizer.telegram_id, NotificationType.REGISTRATION_CONFIRMED)
        ]

    @pytest.mark.parametrize(
        "fields",
        [
            {"status": "cancelled", "cancellation_reason": "Погода"},
            {"status": "completed"},
            {"starts_at": past()},
        ],
    )
    async def test_closed_event_rejects_registration(
        self, api: AsyncClient, factory: Factory, fields: dict[str, Any]
    ) -> None:
        """На отменённое, завершённое и начавшееся мероприятие записаться нельзя."""
        _, event = await event_of(factory, **fields)
        volunteer = await factory.user()

        response = await api.post(url(event), headers=as_user(volunteer))

        assert response.status_code == 409

    async def test_unknown_event_is_not_found(self, api: AsyncClient, factory: Factory) -> None:
        """Несуществующее мероприятие — 404."""
        volunteer = await factory.user()

        response = await api.post("/api/events/999999/registrations", headers=as_user(volunteer))

        assert response.status_code == 404

    async def test_requires_registered_user(self, api: AsyncClient, factory: Factory) -> None:
        """Без заголовка X-Telegram-Id записаться нельзя."""
        _, event = await event_of(factory)

        response = await api.post(url(event))

        assert response.status_code == 401


class TestReminders:
    """Напоминания: время рассчитывает бэкенд, отправляет бот."""

    async def test_confirmed_registration_schedules_a_reminder(
        self, api: AsyncClient, factory: Factory, published: FakePublisher
    ) -> None:
        """После записи волонтёру назначается напоминание за сутки до начала."""
        starts_at = datetime.now(UTC) + timedelta(days=3)
        _, event = await event_of(factory, starts_at=starts_at)
        volunteer = await factory.user()

        await api.post(url(event), headers=as_user(volunteer))

        (reminder,) = [m for m in published.messages if m.type is NotificationType.REMINDER]
        assert reminder.telegram_id == volunteer.telegram_id
        assert reminder.key == f"reminder:{event.id}"
        assert reminder.send_at is not None
        assert abs(reminder.send_at - (starts_at - timedelta(hours=24))) < timedelta(seconds=1)

    async def test_no_reminder_when_event_is_too_close(
        self, api: AsyncClient, factory: Factory, published: FakePublisher
    ) -> None:
        """Если до начала меньше суток, напоминание не назначается."""
        _, event = await event_of(factory, starts_at=datetime.now(UTC) + timedelta(hours=5))
        volunteer = await factory.user()

        await api.post(url(event), headers=as_user(volunteer))

        assert NotificationType.REMINDER not in types(published.messages)

    @pytest.mark.parametrize("approval", [True, False])
    async def test_only_confirmed_places_get_reminders(
        self, api: AsyncClient, factory: Factory, published: FakePublisher, approval: bool
    ) -> None:
        """Заявка без решения и лист ожидания напоминаний не получают."""
        _, event = await event_of(
            factory,
            starts_at=datetime.now(UTC) + timedelta(days=3),
            capacity=1,
            is_approval_required=approval,
        )
        await fill(factory, event, 1)
        waiting = await factory.user()

        await api.post(url(event), headers=as_user(waiting))

        assert NotificationType.REMINDER not in types(published.messages)

    async def test_pending_request_gets_a_reminder_after_approval(
        self, api: AsyncClient, factory: Factory, published: FakePublisher
    ) -> None:
        """Напоминание назначается, когда организатор одобрил заявку."""
        organizer, event = await event_of(
            factory, starts_at=datetime.now(UTC) + timedelta(days=3), is_approval_required=True
        )
        volunteer = await factory.user()
        created = await api.post(url(event), headers=as_user(volunteer))
        assert NotificationType.REMINDER not in types(published.messages)

        await api.post(url(event, f"/{created.json()['id']}/approve"), headers=as_user(organizer))

        (reminder,) = [m for m in published.messages if m.type is NotificationType.REMINDER]
        assert reminder.telegram_id == volunteer.telegram_id


class TestClaim:
    """Занятие освободившегося места."""

    async def test_waitlisted_user_takes_free_place(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Когда место освободилось, ожидающий занимает его сам."""
        _, event = await event_of(factory, capacity=1)
        holder, waiting = await factory.user(), await factory.user()
        await api.post(url(event), headers=as_user(holder))
        await api.post(url(event), headers=as_user(waiting))
        await api.post(url(event, "/me/cancel"), json={"reason": "Занят"}, headers=as_user(holder))

        response = await api.post(url(event, "/me/claim"), headers=as_user(waiting))

        assert response.status_code == 200
        assert response.json()["status"] == "registered"

    async def test_claim_with_approval_becomes_pending(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """В мероприятии с одобрением занятое место превращается в заявку."""
        _, event = await event_of(factory, capacity=1, is_approval_required=True)
        waiting = await factory.user()
        await factory.registration(event, waiting, status=RegistrationStatus.WAITLISTED)

        response = await api.post(url(event, "/me/claim"), headers=as_user(waiting))

        assert response.json()["status"] == "pending"

    async def test_claim_without_free_places_is_conflict(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Если место успели занять, ответ — 409, пользователь остаётся в листе."""
        _, event = await event_of(factory, capacity=1)
        await fill(factory, event, 1)
        waiting = await factory.user()
        await factory.registration(event, waiting, status=RegistrationStatus.WAITLISTED)

        response = await api.post(url(event, "/me/claim"), headers=as_user(waiting))
        own = await api.get(url(event, "/me"), headers=as_user(waiting))

        assert response.status_code == 409
        assert own.json()["status"] == "waitlisted"

    async def test_only_waitlisted_can_claim(self, api: AsyncClient, factory: Factory) -> None:
        """Занять место может только тот, кто в листе ожидания."""
        _, event = await event_of(factory)
        volunteer = await factory.user()
        await factory.registration(event, volunteer)

        response = await api.post(url(event, "/me/claim"), headers=as_user(volunteer))

        assert response.status_code == 409

    async def test_claim_without_registration_is_not_found(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Без записи занять место нельзя."""
        _, event = await event_of(factory)
        volunteer = await factory.user()

        response = await api.post(url(event, "/me/claim"), headers=as_user(volunteer))

        assert response.status_code == 404


class TestCancel:
    """Отмена своей записи."""

    async def test_cancel_records_reason_and_frees_place(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Отмена сохраняет причину и освобождает место."""
        _, event = await event_of(factory, capacity=2)
        volunteer = await factory.user()
        await api.post(url(event), headers=as_user(volunteer))

        response = await api.post(
            url(event, "/me/cancel"), json={"reason": "Заболел"}, headers=as_user(volunteer)
        )
        card = await api.get(f"/api/events/{event.id}", headers=as_user(volunteer))

        body = response.json()
        assert body["status"] == "cancelled"
        assert body["cancellation_reason"] == "Заболел"
        assert body["cancelled_at"] is not None
        assert card.json()["occupied"] == 0

    async def test_organizer_and_waitlist_are_notified(
        self, api: AsyncClient, factory: Factory, published: FakePublisher
    ) -> None:
        """Организатор узнаёт об отмене, а лист ожидания — об освободившемся месте."""
        organizer, event = await event_of(factory, capacity=1)
        holder, waiting = await factory.user(), await factory.user()
        await api.post(url(event), headers=as_user(holder))
        await api.post(url(event), headers=as_user(waiting))

        await api.post(url(event, "/me/cancel"), json={"reason": "Занят"}, headers=as_user(holder))

        sent = published.messages
        pairs = [(n.telegram_id, n.type) for n in sent]
        assert (organizer.telegram_id, NotificationType.ORGANIZER_CANCELLATION) in pairs
        assert (holder.telegram_id, NotificationType.REGISTRATION_CANCELLED) in pairs
        assert (waiting.telegram_id, NotificationType.SPOT_FREED) in pairs
        cancellation = next(n for n in sent if n.type is NotificationType.ORGANIZER_CANCELLATION)
        assert cancellation.payload is not None
        assert cancellation.payload["reason"] == "Занят"

    async def test_cancelling_waitlist_does_not_announce_free_place(
        self, api: AsyncClient, factory: Factory, published: FakePublisher
    ) -> None:
        """Отмена из листа ожидания не освобождает места, предложения нет."""
        _, event = await event_of(factory, capacity=1)
        await fill(factory, event, 1)
        waiting, other = await factory.user(), await factory.user()
        await factory.registration(event, waiting, status=RegistrationStatus.WAITLISTED)
        await factory.registration(event, other, status=RegistrationStatus.WAITLISTED)

        await api.post(
            url(event, "/me/cancel"), json={"reason": "Передумал"}, headers=as_user(waiting)
        )

        assert NotificationType.SPOT_FREED not in types(published.messages)

    async def test_pending_cancellation_frees_place(
        self, api: AsyncClient, factory: Factory, published: FakePublisher
    ) -> None:
        """Отмена заявки, ожидающей одобрения, тоже освобождает место."""
        _, event = await event_of(factory, capacity=1, is_approval_required=True)
        waiting = await factory.user()
        applicant = await factory.user()
        await api.post(url(event), headers=as_user(applicant))
        await factory.registration(event, waiting, status=RegistrationStatus.WAITLISTED)

        await api.post(
            url(event, "/me/cancel"), json={"reason": "Передумал"}, headers=as_user(applicant)
        )

        assert NotificationType.SPOT_FREED in types(published.messages)

    async def test_reason_is_required(self, api: AsyncClient, factory: Factory) -> None:
        """Без причины отменить запись нельзя."""
        _, event = await event_of(factory)
        volunteer = await factory.user()
        await api.post(url(event), headers=as_user(volunteer))

        missing = await api.post(url(event, "/me/cancel"), json={}, headers=as_user(volunteer))
        blank = await api.post(
            url(event, "/me/cancel"), json={"reason": " "}, headers=as_user(volunteer)
        )

        assert missing.status_code == 422
        assert blank.status_code == 422

    async def test_cancel_without_registration_is_not_found(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Отменять нечего — 404."""
        _, event = await event_of(factory)
        volunteer = await factory.user()

        response = await api.post(
            url(event, "/me/cancel"), json={"reason": "Нет"}, headers=as_user(volunteer)
        )

        assert response.status_code == 404

    async def test_cancel_twice_is_conflict(self, api: AsyncClient, factory: Factory) -> None:
        """Повторная отмена — 409."""
        _, event = await event_of(factory)
        volunteer = await factory.user()
        await api.post(url(event), headers=as_user(volunteer))
        body = {"reason": "Заболел"}
        await api.post(url(event, "/me/cancel"), json=body, headers=as_user(volunteer))

        response = await api.post(url(event, "/me/cancel"), json=body, headers=as_user(volunteer))

        assert response.status_code == 409

    async def test_cannot_cancel_after_start(self, api: AsyncClient, factory: Factory) -> None:
        """После начала мероприятия запись не отменить."""
        _, event = await event_of(factory, starts_at=past())
        volunteer = await factory.user()
        await factory.registration(event, volunteer)

        response = await api.post(
            url(event, "/me/cancel"), json={"reason": "Поздно"}, headers=as_user(volunteer)
        )

        assert response.status_code == 409

    async def test_organizer_is_not_notified_about_own_cancellation(
        self, api: AsyncClient, factory: Factory, published: FakePublisher
    ) -> None:
        """Организатор, отменивший свою запись, не получает сообщение о себе."""
        organizer, event = await event_of(factory)
        await api.post(url(event), headers=as_user(organizer))

        await api.post(
            url(event, "/me/cancel"), json={"reason": "Дела"}, headers=as_user(organizer)
        )

        assert NotificationType.ORGANIZER_CANCELLATION not in types(published.messages)


class TestDecision:
    """Одобрение и отклонение заявок."""

    async def pending(self, api: AsyncClient, factory: Factory) -> tuple[User, Event, User, int]:
        organizer, event = await event_of(factory, is_approval_required=True, capacity=1)
        volunteer = await factory.user()
        created = await api.post(url(event), headers=as_user(volunteer))

        return organizer, event, volunteer, created.json()["id"]

    async def test_owner_approves(
        self, api: AsyncClient, factory: Factory, published: FakePublisher
    ) -> None:
        """Организатор одобряет заявку: статус registered, решение записано, волонтёр уведомлён."""
        organizer, event, volunteer, registration_id = await self.pending(api, factory)

        response = await api.post(
            url(event, f"/{registration_id}/approve"), headers=as_user(organizer)
        )

        body = response.json()
        assert body["status"] == "registered"
        assert body["decided_at"] is not None
        assert body["user"]["id"] == volunteer.id
        sent = published.messages
        assert (volunteer.telegram_id, NotificationType.REGISTRATION_APPROVED) in [
            (n.telegram_id, n.type) for n in sent
        ]

    async def test_owner_rejects_with_comment(
        self, api: AsyncClient, factory: Factory, published: FakePublisher
    ) -> None:
        """Отказ сохраняет комментарий, уведомляет волонтёра и освобождает место."""
        organizer, event, volunteer, registration_id = await self.pending(api, factory)
        waiting = await factory.user()
        await factory.registration(event, waiting, status=RegistrationStatus.WAITLISTED)

        response = await api.post(
            url(event, f"/{registration_id}/reject"),
            json={"comment": "Нет мест для новичков"},
            headers=as_user(organizer),
        )

        body = response.json()
        assert body["status"] == "rejected"
        assert body["decision_comment"] == "Нет мест для новичков"
        sent = [(n.telegram_id, n.type) for n in published.messages]
        assert (volunteer.telegram_id, NotificationType.REGISTRATION_REJECTED) in sent
        assert (waiting.telegram_id, NotificationType.SPOT_FREED) in sent

    async def test_reject_requires_comment(self, api: AsyncClient, factory: Factory) -> None:
        """Отклонить без комментария нельзя."""
        organizer, event, _, registration_id = await self.pending(api, factory)

        response = await api.post(
            url(event, f"/{registration_id}/reject"), json={}, headers=as_user(organizer)
        )

        assert response.status_code == 422

    @pytest.mark.parametrize("action", ["approve", "reject"])
    async def test_only_responsible_organizer_decides(
        self, api: AsyncClient, factory: Factory, action: str
    ) -> None:
        """Решение принимает только создатель мероприятия: ни другой организатор, ни админ."""
        _, event, _, registration_id = await self.pending(api, factory)
        admin = await make_admin(factory)
        other = await make_organizer(factory, admin)
        volunteer = await factory.user()
        body = {"comment": "Нет"} if action == "reject" else None

        for user in (other, admin, volunteer):
            response = await api.post(
                url(event, f"/{registration_id}/{action}"), json=body, headers=as_user(user)
            )
            assert response.status_code == 403

    async def test_only_pending_can_be_decided(self, api: AsyncClient, factory: Factory) -> None:
        """Решение возможно только по заявке, ожидающей одобрения."""
        organizer, event = await event_of(factory)
        volunteer = await factory.user()
        registration = await factory.registration(event, volunteer)

        response = await api.post(
            url(event, f"/{registration.id}/approve"), headers=as_user(organizer)
        )

        assert response.status_code == 409

    async def test_unknown_registration_is_not_found(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Несуществующая запись — 404."""
        organizer, event = await event_of(factory)

        response = await api.post(url(event, "/999999/approve"), headers=as_user(organizer))

        assert response.status_code == 404

    async def test_registration_of_another_event_is_not_found(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Запись другого мероприятия через это мероприятие не найти."""
        organizer, event = await event_of(factory)
        other_event = await factory.event(organizer=organizer, is_approval_required=True)
        registration = await factory.registration(
            other_event, await factory.user(), status=RegistrationStatus.PENDING
        )

        response = await api.post(
            url(event, f"/{registration.id}/approve"), headers=as_user(organizer)
        )

        assert response.status_code == 404

    async def test_cancelled_event_cannot_be_decided(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """По отменённому мероприятию решений не принимают."""
        organizer, event = await event_of(factory, status="cancelled", cancellation_reason="Погода")
        registration = await factory.registration(
            event, await factory.user(), status=RegistrationStatus.PENDING
        )

        response = await api.post(
            url(event, f"/{registration.id}/approve"), headers=as_user(organizer)
        )

        assert response.status_code == 409

    async def test_unknown_event_is_not_found(self, api: AsyncClient, factory: Factory) -> None:
        """Несуществующее мероприятие — 404."""
        admin = await make_admin(factory)

        response = await api.post(
            "/api/events/999999/registrations/1/approve", headers=as_user(admin)
        )

        assert response.status_code == 404


class TestAttendance:
    """Отметка посещаемости."""

    async def test_owner_marks_attended_and_absent(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """После начала организатор отмечает, пришёл ли участник; отметку можно исправить."""
        organizer, event = await event_of(factory, starts_at=past())
        registration = await factory.registration(event, await factory.user())
        mark = url(event, f"/{registration.id}/attendance")

        attended = await api.post(mark, json={"attended": True}, headers=as_user(organizer))
        absent = await api.post(mark, json={"attended": False}, headers=as_user(organizer))

        assert attended.json()["status"] == "attended"
        assert absent.json()["status"] == "absent"

    async def test_admin_can_mark(self, api: AsyncClient, factory: Factory) -> None:
        """Администратор тоже может отметить посещение."""
        _, event = await event_of(factory, starts_at=past())
        registration = await factory.registration(event, await factory.user())
        admin = await make_admin(factory)

        response = await api.post(
            url(event, f"/{registration.id}/attendance"),
            json={"attended": True},
            headers=as_user(admin),
        )

        assert response.status_code == 200

    async def test_works_for_completed_event(self, api: AsyncClient, factory: Factory) -> None:
        """Отметки можно проставлять и после завершения мероприятия."""
        organizer, event = await event_of(factory, starts_at=past(), status="completed")
        registration = await factory.registration(event, await factory.user())

        response = await api.post(
            url(event, f"/{registration.id}/attendance"),
            json={"attended": True},
            headers=as_user(organizer),
        )

        assert response.status_code == 200

    async def test_other_organizer_and_volunteer_cannot_mark(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Чужой организатор и волонтёр отметки ставить не могут."""
        _, event = await event_of(factory, starts_at=past())
        registration = await factory.registration(event, await factory.user())
        other = await make_organizer(factory, await make_admin(factory))
        volunteer = await factory.user()

        for user in (other, volunteer):
            response = await api.post(
                url(event, f"/{registration.id}/attendance"),
                json={"attended": True},
                headers=as_user(user),
            )
            assert response.status_code == 403

    async def test_cannot_mark_before_start(self, api: AsyncClient, factory: Factory) -> None:
        """До начала мероприятия посещение отметить нельзя."""
        organizer, event = await event_of(factory)
        registration = await factory.registration(event, await factory.user())

        response = await api.post(
            url(event, f"/{registration.id}/attendance"),
            json={"attended": True},
            headers=as_user(organizer),
        )

        assert response.status_code == 409

    async def test_cannot_mark_cancelled_event(self, api: AsyncClient, factory: Factory) -> None:
        """У отменённого мероприятия посещаемости нет."""
        organizer, event = await event_of(
            factory, starts_at=past(), status="cancelled", cancellation_reason="Погода"
        )
        registration = await factory.registration(event, await factory.user())

        response = await api.post(
            url(event, f"/{registration.id}/attendance"),
            json={"attended": True},
            headers=as_user(organizer),
        )

        assert response.status_code == 409

    @pytest.mark.parametrize("status", [RegistrationStatus.PENDING, RegistrationStatus.WAITLISTED])
    async def test_only_participants_can_be_marked(
        self, api: AsyncClient, factory: Factory, status: RegistrationStatus
    ) -> None:
        """Отметить можно только записанных участников."""
        organizer, event = await event_of(factory, starts_at=past())
        registration = await factory.registration(event, await factory.user(), status=status)

        response = await api.post(
            url(event, f"/{registration.id}/attendance"),
            json={"attended": True},
            headers=as_user(organizer),
        )

        assert response.status_code == 409

    async def test_unknown_registration_is_not_found(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Несуществующая запись — 404."""
        organizer, event = await event_of(factory, starts_at=past())

        response = await api.post(
            url(event, "/999999/attendance"), json={"attended": True}, headers=as_user(organizer)
        )

        assert response.status_code == 404


class TestParticipants:
    """Список записавшихся."""

    async def test_staff_sees_participants_with_contacts(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Организатор видит записавшихся с контактами в порядке записи."""
        organizer, event = await event_of(factory)
        first = await factory.user(full_name="Первый", phone="+79990000001")
        second = await factory.user(full_name="Второй", phone="+79990000002")
        await factory.registration(event, first)
        await factory.registration(event, second)

        response = await api.get(url(event), headers=as_user(organizer))

        body = response.json()
        assert body["total"] == 2
        assert [item["user"]["full_name"] for item in body["items"]] == ["Первый", "Второй"]
        assert body["items"][0]["user"]["phone"] == "+79990000001"

    async def test_filter_by_status(self, api: AsyncClient, factory: Factory) -> None:
        """Фильтр по одному или нескольким статусам."""
        organizer, event = await event_of(factory)
        await factory.registration(event, await factory.user())
        await factory.registration(
            event, await factory.user(), status=RegistrationStatus.WAITLISTED
        )
        await factory.registration(event, await factory.user(), status=RegistrationStatus.PENDING)

        waitlisted = await api.get(url(event) + "?status=waitlisted", headers=as_user(organizer))
        both = await api.get(
            url(event) + "?status=waitlisted&status=pending", headers=as_user(organizer)
        )

        assert waitlisted.json()["total"] == 1
        assert both.json()["total"] == 2

    async def test_pagination(self, api: AsyncClient, factory: Factory) -> None:
        """Постраничная выборка возвращает общее число."""
        organizer, event = await event_of(factory, capacity=10)
        await fill(factory, event, 3)

        response = await api.get(url(event) + "?limit=2&offset=2", headers=as_user(organizer))

        assert response.json()["total"] == 3
        assert len(response.json()["items"]) == 1

    async def test_volunteer_cannot_see_participants(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Волонтёру список участников недоступен."""
        _, event = await event_of(factory)
        volunteer = await factory.user()

        response = await api.get(url(event), headers=as_user(volunteer))

        assert response.status_code == 403

    async def test_unknown_event_is_not_found(self, api: AsyncClient, factory: Factory) -> None:
        """Несуществующее мероприятие — 404."""
        admin = await make_admin(factory)

        response = await api.get("/api/events/999999/registrations", headers=as_user(admin))

        assert response.status_code == 404


class TestOwnRegistrations:
    """Свои записи."""

    async def test_own_registration_of_event(self, api: AsyncClient, factory: Factory) -> None:
        """Запись пользователя на мероприятие."""
        _, event = await event_of(factory)
        volunteer = await factory.user()
        await api.post(url(event), headers=as_user(volunteer))

        response = await api.get(url(event, "/me"), headers=as_user(volunteer))

        assert response.json()["status"] == "registered"

    async def test_no_registration_is_not_found(self, api: AsyncClient, factory: Factory) -> None:
        """Если записи нет, ответ 404."""
        _, event = await event_of(factory)
        volunteer = await factory.user()

        response = await api.get(url(event, "/me"), headers=as_user(volunteer))

        assert response.status_code == 404

    async def test_unknown_event_is_not_found(self, api: AsyncClient, factory: Factory) -> None:
        """Несуществующее мероприятие — 404."""
        volunteer = await factory.user()

        response = await api.get("/api/events/999999/registrations/me", headers=as_user(volunteer))

        assert response.status_code == 404

    async def test_list_has_events_and_newest_first(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Список записей содержит мероприятия и идёт от новых к старым."""
        organizer, first = await event_of(factory, title="Первое")
        second = await factory.event(organizer=organizer, title="Второе")
        volunteer = await factory.user()
        await api.post(url(first), headers=as_user(volunteer))
        await api.post(url(second), headers=as_user(volunteer))

        response = await api.get("/api/registrations/me", headers=as_user(volunteer))

        items = response.json()["items"]
        assert [item["event"]["title"] for item in items] == ["Второе", "Первое"]
        assert items[0]["event"]["occupied"] == 1

    async def test_list_contains_only_own_registrations(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Чужие записи в списке не появляются."""
        _, event = await event_of(factory)
        mine, other = await factory.user(), await factory.user()
        await api.post(url(event), headers=as_user(other))

        response = await api.get("/api/registrations/me", headers=as_user(mine))

        assert response.json() == {"items": [], "total": 0, "limit": 20, "offset": 0}

    async def test_list_filters_by_status(self, api: AsyncClient, factory: Factory) -> None:
        """Фильтр по статусу."""
        organizer, active = await event_of(factory)
        cancelled = await factory.event(organizer=organizer)
        volunteer = await factory.user()
        await api.post(url(active), headers=as_user(volunteer))
        await api.post(url(cancelled), headers=as_user(volunteer))
        await api.post(
            url(cancelled, "/me/cancel"), json={"reason": "Передумал"}, headers=as_user(volunteer)
        )

        response = await api.get(
            "/api/registrations/me?status=cancelled", headers=as_user(volunteer)
        )

        assert [item["event_id"] for item in response.json()["items"]] == [cancelled.id]
