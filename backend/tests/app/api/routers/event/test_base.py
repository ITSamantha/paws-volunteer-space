from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Bonus, Event, Tag, User
from app.database.models.enums import NotificationType, RegistrationStatus
from tests.app.api.support import as_user, make_admin, make_organizer
from tests.app.conftest import FakePublisher
from tests.app.database.factory import Factory

pytestmark = pytest.mark.integration


def in_days(days: float) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).isoformat()


def payload(**fields: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "title": "Выезд в приют",
        "starts_at": in_days(3),
        "location": "Остановка у метро",
        "capacity": 5,
    }

    return {**values, **fields}


async def organizer_with_event(
    factory: Factory, admin: User | None = None, **fields: Any
) -> tuple[User, Event]:
    organizer = await make_organizer(factory, admin or await make_admin(factory))
    event = await factory.event(organizer=organizer, **fields)

    return organizer, event


class TestEventList:
    """Список мероприятий."""

    async def test_events_are_sorted_by_start(self, api: AsyncClient, factory: Factory) -> None:
        """Список идёт по возрастанию даты начала."""
        now = datetime.now(UTC)
        await factory.event(title="Позже", starts_at=now + timedelta(days=5))
        await factory.event(title="Раньше", starts_at=now + timedelta(days=1))
        volunteer = await factory.user()

        response = await api.get("/api/events", headers=as_user(volunteer))

        assert [item["title"] for item in response.json()["items"]] == ["Раньше", "Позже"]

    async def test_list_item_hides_card_details(self, api: AsyncClient, factory: Factory) -> None:
        """В списке нет описания, инструкции и ссылки на чат: они только в карточке."""
        await factory.event(telegram_chat_link="https://t.me/chat", description="Подробно")
        volunteer = await factory.user()

        response = await api.get("/api/events", headers=as_user(volunteer))

        item = response.json()["items"][0]
        assert "telegram_chat_link" not in item
        assert "description" not in item
        assert {"id", "title", "starts_at", "capacity", "occupied", "status"} <= set(item)

    async def test_occupied_counts_only_places_in_use(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Место занимают записанные, ожидающие одобрения и посетившие."""
        event = await factory.event(capacity=10)
        statuses = {
            RegistrationStatus.REGISTERED: 2,
            RegistrationStatus.PENDING: 1,
            RegistrationStatus.ATTENDED: 1,
            RegistrationStatus.WAITLISTED: 1,
            RegistrationStatus.REJECTED: 1,
            RegistrationStatus.ABSENT: 1,
        }
        for status, count in statuses.items():
            for _ in range(count):
                extra: dict[str, Any] = {}
                if status is RegistrationStatus.REJECTED:
                    extra = {
                        "decided_by": event.created_by,
                        "decided_at": datetime.now(UTC),
                        "decision_comment": "Нет",
                    }
                await factory.registration(event, await factory.user(), status=status, **extra)
        volunteer = await factory.user()

        response = await api.get("/api/events", headers=as_user(volunteer))

        assert response.json()["items"][0]["occupied"] == 4

    async def test_filter_by_status(self, api: AsyncClient, factory: Factory) -> None:
        """Фильтр по статусу."""
        await factory.event(title="Идёт набор")
        await factory.event(title="Отменено", status="cancelled", cancellation_reason="Погода")
        volunteer = await factory.user()

        response = await api.get("/api/events?status=cancelled", headers=as_user(volunteer))

        assert [item["title"] for item in response.json()["items"]] == ["Отменено"]

    async def test_filter_by_shelter(self, api: AsyncClient, factory: Factory) -> None:
        """Фильтр по приюту."""
        shelter = await factory.shelter()
        await factory.event(title="В приюте", shelter_id=shelter.id)
        await factory.event(title="Без приюта")
        volunteer = await factory.user()

        response = await api.get(f"/api/events?shelter_id={shelter.id}", headers=as_user(volunteer))

        assert [item["title"] for item in response.json()["items"]] == ["В приюте"]

    async def test_filter_by_dates(self, api: AsyncClient, factory: Factory) -> None:
        """Фильтр по диапазону дат начала."""
        now = datetime.now(UTC)
        await factory.event(title="Рано", starts_at=now + timedelta(days=1))
        await factory.event(title="В срок", starts_at=now + timedelta(days=5))
        await factory.event(title="Поздно", starts_at=now + timedelta(days=9))
        volunteer = await factory.user()
        start = (now + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
        end = (now + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")

        response = await api.get(
            f"/api/events?starts_from={start}&starts_to={end}", headers=as_user(volunteer)
        )

        assert [item["title"] for item in response.json()["items"]] == ["В срок"]

    async def test_naive_date_filter_is_rejected(self, api: AsyncClient, factory: Factory) -> None:
        """Дата без часового пояса в фильтре отклоняется."""
        volunteer = await factory.user()

        response = await api.get(
            "/api/events?starts_from=2030-01-01T10:00:00", headers=as_user(volunteer)
        )

        assert response.status_code == 422

    async def test_filter_by_tag_and_bonus(
        self, api: AsyncClient, factory: Factory, session: AsyncSession
    ) -> None:
        """Фильтры по тегу и бонусу."""
        tag = Tag(title="Собаки")
        bonus = Bonus(title="ПГАС")
        session.add_all([tag, bonus])
        await session.flush()
        tagged = await factory.event(title="С тегом")
        await factory.event(title="Без тега")
        bonused = await factory.event(title="С бонусом")
        await session.refresh(tagged, ["tags"])
        await session.refresh(bonused, ["bonuses"])
        tagged.tags.append(tag)
        bonused.bonuses.append(bonus)
        await session.flush()
        volunteer = await factory.user()

        by_tag = await api.get(f"/api/events?tag_id={tag.id}", headers=as_user(volunteer))
        by_bonus = await api.get(f"/api/events?bonus_id={bonus.id}", headers=as_user(volunteer))

        assert [i["title"] for i in by_tag.json()["items"]] == ["С тегом"]
        assert [i["title"] for i in by_bonus.json()["items"]] == ["С бонусом"]

    async def test_pagination(self, api: AsyncClient, factory: Factory) -> None:
        """Постраничная выборка возвращает общее число."""
        for number in range(3):
            await factory.event(
                title=f"Выезд {number}", starts_at=datetime.now(UTC) + timedelta(days=number + 1)
            )
        volunteer = await factory.user()

        response = await api.get("/api/events?limit=2&offset=2", headers=as_user(volunteer))

        body = response.json()
        assert body["total"] == 3
        assert [item["title"] for item in body["items"]] == ["Выезд 2"]

    async def test_requires_registered_user(self, api: AsyncClient) -> None:
        """Без заголовка X-Telegram-Id список недоступен."""
        response = await api.get("/api/events")

        assert response.status_code == 401


class TestEventCard:
    """Карточка мероприятия."""

    async def test_card_has_shelter_bonuses_and_tags(
        self, api: AsyncClient, factory: Factory, session: AsyncSession
    ) -> None:
        """В карточке приют, бонусы и теги."""
        admin = await make_admin(factory)
        shelter = await factory.shelter(title="Лапы", address="Адрес")
        bonus = Bonus(title="ПГАС")
        tag = Tag(title="Выезд")
        session.add_all([bonus, tag])
        await session.flush()
        created = await api.post(
            "/api/events",
            json=payload(shelter_id=shelter.id, bonus_ids=[bonus.id], tag_ids=[tag.id]),
            headers=as_user(admin),
        )
        volunteer = await factory.user()

        response = await api.get(f"/api/events/{created.json()['id']}", headers=as_user(volunteer))

        body = response.json()
        assert body["shelter"] == {"id": shelter.id, "title": "Лапы", "address": "Адрес"}
        assert [b["title"] for b in body["bonuses"]] == ["ПГАС"]
        assert [t["title"] for t in body["tags"]] == ["Выезд"]
        assert body["status"] == "planned"

    @pytest.mark.parametrize(
        ("status", "visible"),
        [
            (RegistrationStatus.REGISTERED, True),
            (RegistrationStatus.ATTENDED, True),
            (RegistrationStatus.PENDING, False),
            (RegistrationStatus.WAITLISTED, False),
            (RegistrationStatus.CANCELLED, False),
        ],
    )
    async def test_chat_is_visible_only_to_confirmed_participants(
        self,
        api: AsyncClient,
        factory: Factory,
        status: RegistrationStatus,
        visible: bool,
    ) -> None:
        """Ссылку на чат видят только подтверждённые участники."""
        event = await factory.event(telegram_chat_link="https://t.me/chat")
        user = await factory.user()
        extra: dict[str, Any] = {}
        if status is RegistrationStatus.CANCELLED:
            extra = {"cancelled_at": datetime.now(UTC), "cancellation_reason": "Передумал"}
        await factory.registration(event, user, status=status, **extra)

        response = await api.get(f"/api/events/{event.id}", headers=as_user(user))

        expected = "https://t.me/chat" if visible else None
        assert response.json()["telegram_chat_link"] == expected

    async def test_chat_is_hidden_from_unregistered_volunteer(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Волонтёр без записи ссылку на чат не видит."""
        event = await factory.event(telegram_chat_link="https://t.me/chat")
        volunteer = await factory.user()

        response = await api.get(f"/api/events/{event.id}", headers=as_user(volunteer))

        assert response.json()["telegram_chat_link"] is None

    async def test_chat_is_visible_to_staff(self, api: AsyncClient, factory: Factory) -> None:
        """Организаторы и администраторы видят ссылку на чат всегда."""
        event = await factory.event(telegram_chat_link="https://t.me/chat")
        admin = await make_admin(factory)

        response = await api.get(f"/api/events/{event.id}", headers=as_user(admin))

        assert response.json()["telegram_chat_link"] == "https://t.me/chat"

    async def test_unknown_event_is_not_found(self, api: AsyncClient, factory: Factory) -> None:
        """Несуществующее мероприятие — 404."""
        volunteer = await factory.user()

        response = await api.get("/api/events/999999", headers=as_user(volunteer))

        assert response.status_code == 404


class TestEventCreate:
    """Создание мероприятия."""

    async def test_organizer_creates_event(self, api: AsyncClient, factory: Factory) -> None:
        """Организатор создаёт мероприятие, и оно запоминает автора."""
        organizer = await make_organizer(factory, await make_admin(factory))

        response = await api.post("/api/events", json=payload(), headers=as_user(organizer))

        body = response.json()
        assert response.status_code == 201
        assert body["created_by"] == organizer.id
        assert body["status"] == "planned"
        assert body["occupied"] == 0
        assert body["is_approval_required"] is False

    async def test_creator_sees_chat_link(self, api: AsyncClient, factory: Factory) -> None:
        """Создатель сразу видит ссылку на чат в ответе."""
        admin = await make_admin(factory)

        response = await api.post(
            "/api/events",
            json=payload(telegram_chat_link="https://t.me/chat"),
            headers=as_user(admin),
        )

        assert response.json()["telegram_chat_link"] == "https://t.me/chat"

    async def test_shelter_defaults_are_applied(self, api: AsyncClient, factory: Factory) -> None:
        """Одобрение записей и инструкция берутся из приюта, если не указаны."""
        admin = await make_admin(factory)
        shelter = await factory.shelter(is_approval_required=True, instructions="Сменная обувь")

        response = await api.post(
            "/api/events", json=payload(shelter_id=shelter.id), headers=as_user(admin)
        )

        body = response.json()
        assert body["is_approval_required"] is True
        assert body["instructions"] == "Сменная обувь"

    async def test_explicit_values_override_shelter_defaults(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Явно указанные значения важнее значений приюта."""
        admin = await make_admin(factory)
        shelter = await factory.shelter(is_approval_required=True, instructions="Сменная обувь")

        response = await api.post(
            "/api/events",
            json=payload(shelter_id=shelter.id, is_approval_required=False, instructions="Другое"),
            headers=as_user(admin),
        )

        body = response.json()
        assert body["is_approval_required"] is False
        assert body["instructions"] == "Другое"

    async def test_shelter_without_location_is_enough(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Место встречи можно не указывать, если есть приют."""
        admin = await make_admin(factory)
        shelter = await factory.shelter()
        data = payload(shelter_id=shelter.id)
        del data["location"]

        response = await api.post("/api/events", json=data, headers=as_user(admin))

        assert response.status_code == 201
        assert response.json()["location"] is None

    async def test_volunteer_cannot_create(self, api: AsyncClient, factory: Factory) -> None:
        """Волонтёр не может создавать мероприятия."""
        volunteer = await factory.user()

        response = await api.post("/api/events", json=payload(), headers=as_user(volunteer))

        assert response.status_code == 403

    @pytest.mark.parametrize(
        "changes",
        [
            {"title": ""},
            {"capacity": 0},
            {"capacity": 1001},
            {"starts_at": "2030-01-01T10:00:00"},
            {"ends_at": in_days(2)},
            {"event_link": "ftp://dobro.ru/1"},
            {"event_link": "dobro.ru/1"},
            {"telegram_chat_link": "https://example.org/chat"},
            {"telegram_chat_link": "https://t.me/chat/" + "x" * 500},
            {"description": ""},
            {"bonus_ids": list(range(1, 22))},
            {"extra": 1},
        ],
    )
    async def test_invalid_payload_is_rejected(
        self, api: AsyncClient, factory: Factory, changes: dict[str, Any]
    ) -> None:
        """Некорректные данные отклоняются."""
        admin = await make_admin(factory)

        response = await api.post("/api/events", json=payload(**changes), headers=as_user(admin))

        assert response.status_code == 422

    async def test_place_is_required(self, api: AsyncClient, factory: Factory) -> None:
        """Нужен либо приют, либо место встречи."""
        admin = await make_admin(factory)
        data = payload()
        del data["location"]

        response = await api.post("/api/events", json=data, headers=as_user(admin))

        assert response.status_code == 422

    async def test_start_must_be_in_future(self, api: AsyncClient, factory: Factory) -> None:
        """Мероприятие нельзя создать в прошлом."""
        admin = await make_admin(factory)

        response = await api.post(
            "/api/events", json=payload(starts_at=in_days(-1)), headers=as_user(admin)
        )

        assert response.status_code == 422
        assert response.json()["code"] == "unprocessable"

    async def test_unknown_shelter_is_rejected(self, api: AsyncClient, factory: Factory) -> None:
        """Несуществующий приют отклоняется."""
        admin = await make_admin(factory)

        response = await api.post(
            "/api/events", json=payload(shelter_id=999999), headers=as_user(admin)
        )

        assert response.status_code == 422

    async def test_unknown_bonus_and_tag_are_rejected(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Несуществующие бонус и тег отклоняются."""
        admin = await make_admin(factory)

        bonus = await api.post(
            "/api/events", json=payload(bonus_ids=[999999]), headers=as_user(admin)
        )
        tag = await api.post("/api/events", json=payload(tag_ids=[999999]), headers=as_user(admin))

        assert bonus.status_code == 422
        assert tag.status_code == 422

    async def test_repeated_ids_are_allowed(
        self, api: AsyncClient, factory: Factory, session: AsyncSession
    ) -> None:
        """Повтор одного идентификатора не ломает создание."""
        admin = await make_admin(factory)
        tag = Tag(title="Выезд")
        session.add(tag)
        await session.flush()

        response = await api.post(
            "/api/events", json=payload(tag_ids=[tag.id, tag.id]), headers=as_user(admin)
        )

        assert response.status_code == 201
        assert len(response.json()["tags"]) == 1


class TestEventUpdate:
    """Изменение мероприятия."""

    async def test_owner_updates_only_sent_fields(self, api: AsyncClient, factory: Factory) -> None:
        """Организатор мероприятия меняет только переданные поля."""
        organizer, event = await organizer_with_event(factory, title="Старое", capacity=5)

        response = await api.patch(
            f"/api/events/{event.id}", json={"title": "Новое"}, headers=as_user(organizer)
        )

        body = response.json()
        assert body["title"] == "Новое"
        assert body["capacity"] == 5

    async def test_admin_can_update_any_event(self, api: AsyncClient, factory: Factory) -> None:
        """Администратор меняет любое мероприятие."""
        admin = await make_admin(factory)
        _, event = await organizer_with_event(factory, admin)

        response = await api.patch(
            f"/api/events/{event.id}", json={"capacity": 9}, headers=as_user(admin)
        )

        assert response.status_code == 200

    async def test_another_organizer_cannot_update(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Чужое мероприятие организатор менять не может."""
        admin = await make_admin(factory)
        _, event = await organizer_with_event(factory, admin)
        other = await make_organizer(factory, admin)

        response = await api.patch(
            f"/api/events/{event.id}", json={"capacity": 9}, headers=as_user(other)
        )

        assert response.status_code == 403

    async def test_volunteer_cannot_update(self, api: AsyncClient, factory: Factory) -> None:
        """Волонтёр не может менять мероприятие."""
        _, event = await organizer_with_event(factory)
        volunteer = await factory.user()

        response = await api.patch(
            f"/api/events/{event.id}", json={"capacity": 9}, headers=as_user(volunteer)
        )

        assert response.status_code == 403

    async def test_unknown_event_is_not_found(self, api: AsyncClient, factory: Factory) -> None:
        """Несуществующее мероприятие — 404."""
        admin = await make_admin(factory)

        response = await api.patch(
            "/api/events/999999", json={"capacity": 9}, headers=as_user(admin)
        )

        assert response.status_code == 404

    async def test_cancelled_event_cannot_be_changed(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Отменённое мероприятие менять нельзя."""
        organizer, event = await organizer_with_event(
            factory, status="cancelled", cancellation_reason="Погода"
        )

        response = await api.patch(
            f"/api/events/{event.id}", json={"capacity": 9}, headers=as_user(organizer)
        )

        assert response.status_code == 409

    async def test_optional_fields_can_be_cleared(self, api: AsyncClient, factory: Factory) -> None:
        """Необязательные поля очищаются значением null."""
        organizer, event = await organizer_with_event(
            factory, description="Текст", instructions="Взять", comment="Прочее"
        )

        response = await api.patch(
            f"/api/events/{event.id}",
            json={"description": None, "instructions": None, "comment": None},
            headers=as_user(organizer),
        )

        body = response.json()
        assert (body["description"], body["instructions"], body["comment"]) == (None, None, None)

    @pytest.mark.parametrize(
        "field",
        ["title", "starts_at", "capacity", "is_approval_required", "bonus_ids", "tag_ids"],
    )
    async def test_required_fields_cannot_be_cleared(
        self, api: AsyncClient, factory: Factory, field: str
    ) -> None:
        """Обязательные поля нельзя очистить."""
        organizer, event = await organizer_with_event(factory)

        response = await api.patch(
            f"/api/events/{event.id}", json={field: None}, headers=as_user(organizer)
        )

        assert response.status_code == 422

    async def test_shelter_can_be_replaced_and_removed(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Приют можно заменить и убрать, если есть место встречи."""
        organizer, event = await organizer_with_event(factory)
        shelter = await factory.shelter(title="Новый")

        replaced = await api.patch(
            f"/api/events/{event.id}", json={"shelter_id": shelter.id}, headers=as_user(organizer)
        )
        removed = await api.patch(
            f"/api/events/{event.id}", json={"shelter_id": None}, headers=as_user(organizer)
        )

        assert replaced.json()["shelter"]["title"] == "Новый"
        assert removed.json()["shelter"] is None

    async def test_unknown_shelter_is_rejected(self, api: AsyncClient, factory: Factory) -> None:
        """Несуществующий приют отклоняется."""
        organizer, event = await organizer_with_event(factory)

        response = await api.patch(
            f"/api/events/{event.id}", json={"shelter_id": 999999}, headers=as_user(organizer)
        )

        assert response.status_code == 422

    async def test_bonuses_and_tags_are_replaced_as_a_whole(
        self, api: AsyncClient, factory: Factory, session: AsyncSession
    ) -> None:
        """Списки бонусов и тегов заменяются целиком, пустой список убирает всё."""
        organizer, event = await organizer_with_event(factory)
        first, second = Tag(title="Один"), Tag(title="Два")
        bonus = Bonus(title="ПГАС")
        session.add_all([first, second, bonus])
        await session.flush()
        url = f"/api/events/{event.id}"

        await api.patch(
            url, json={"tag_ids": [first.id], "bonus_ids": [bonus.id]}, headers=as_user(organizer)
        )
        replaced = await api.patch(url, json={"tag_ids": [second.id]}, headers=as_user(organizer))
        cleared = await api.patch(url, json={"bonus_ids": []}, headers=as_user(organizer))

        assert [t["title"] for t in replaced.json()["tags"]] == ["Два"]
        assert [b["title"] for b in replaced.json()["bonuses"]] == ["ПГАС"]
        assert cleared.json()["bonuses"] == []

    async def test_unknown_tag_is_rejected(self, api: AsyncClient, factory: Factory) -> None:
        """Несуществующий тег отклоняется."""
        organizer, event = await organizer_with_event(factory)

        response = await api.patch(
            f"/api/events/{event.id}", json={"tag_ids": [999999]}, headers=as_user(organizer)
        )

        assert response.status_code == 422

    @pytest.mark.parametrize(
        "changes",
        [
            {"starts_at": in_days(-1)},
            {"ends_at": in_days(1)},
            {"location": None},
            {"capacity": 0},
            {"event_link": "mailto:a@b.c"},
        ],
    )
    async def test_invalid_changes_are_rejected(
        self, api: AsyncClient, factory: Factory, changes: dict[str, Any]
    ) -> None:
        """Изменения, нарушающие правила, отклоняются."""
        organizer, event = await organizer_with_event(
            factory, starts_at=datetime.now(UTC) + timedelta(days=3)
        )

        response = await api.patch(
            f"/api/events/{event.id}", json=changes, headers=as_user(organizer)
        )

        assert response.status_code == 422

    async def test_capacity_cannot_go_below_occupied_places(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Вместимость нельзя уменьшить ниже числа занятых мест."""
        organizer, event = await organizer_with_event(factory, capacity=5)
        for _ in range(3):
            await factory.registration(event, await factory.user())

        too_small = await api.patch(
            f"/api/events/{event.id}", json={"capacity": 2}, headers=as_user(organizer)
        )
        enough = await api.patch(
            f"/api/events/{event.id}", json={"capacity": 3}, headers=as_user(organizer)
        )

        assert too_small.status_code == 409
        assert enough.status_code == 200

    async def test_participants_are_notified_about_time_change(
        self, api: AsyncClient, factory: Factory, published: FakePublisher
    ) -> None:
        """При смене времени уведомляются записанные, ожидающие и в листе ожидания."""
        organizer, event = await organizer_with_event(factory)
        recipients = {}
        for status in (
            RegistrationStatus.REGISTERED,
            RegistrationStatus.PENDING,
            RegistrationStatus.WAITLISTED,
        ):
            user = await factory.user()
            recipients[status] = user
            await factory.registration(event, user, status=status)
        cancelled = await factory.user()
        await factory.registration(
            event,
            cancelled,
            status=RegistrationStatus.CANCELLED,
            cancelled_at=datetime.now(UTC),
            cancellation_reason="Передумал",
        )

        await api.patch(
            f"/api/events/{event.id}", json={"starts_at": in_days(4)}, headers=as_user(organizer)
        )

        changed = [n for n in published.messages if n.type is NotificationType.EVENT_CHANGED]
        assert {n.telegram_id for n in changed} == {u.telegram_id for u in recipients.values()}
        assert changed[0].payload == {"title": event.title, "changed": ["starts_at"]}

    async def test_confirmed_participants_get_a_new_reminder_when_start_moves(
        self, api: AsyncClient, factory: Factory, published: FakePublisher
    ) -> None:
        """Подтверждённым участникам назначается напоминание на новое время; остальным — нет."""
        organizer, event = await organizer_with_event(factory)
        confirmed, waiting = await factory.user(), await factory.user()
        await factory.registration(event, confirmed)
        await factory.registration(event, waiting, status=RegistrationStatus.WAITLISTED)
        new_start = datetime.now(UTC) + timedelta(days=4)

        await api.patch(
            f"/api/events/{event.id}",
            json={"starts_at": new_start.isoformat()},
            headers=as_user(organizer),
        )

        (reminder,) = [n for n in published.messages if n.type is NotificationType.REMINDER]
        assert reminder.telegram_id == confirmed.telegram_id
        assert reminder.key == f"reminder:{event.id}"
        assert reminder.send_at is not None
        assert abs(reminder.send_at - (new_start - timedelta(hours=24))) < timedelta(seconds=1)

    async def test_no_reminder_when_start_is_less_than_a_day_away(
        self, api: AsyncClient, factory: Factory, published: FakePublisher
    ) -> None:
        """Если до нового начала меньше суток, напоминание не назначается."""
        organizer, event = await organizer_with_event(factory)
        await factory.registration(event, await factory.user())

        await api.patch(
            f"/api/events/{event.id}",
            json={"starts_at": (datetime.now(UTC) + timedelta(hours=5)).isoformat()},
            headers=as_user(organizer),
        )

        assert NotificationType.REMINDER not in {n.type for n in published.messages}

    async def test_each_change_notifies_again(
        self, api: AsyncClient, factory: Factory, published: FakePublisher
    ) -> None:
        """Каждое новое изменение времени отправляет отдельное уведомление."""
        organizer, event = await organizer_with_event(factory)
        await factory.registration(event, await factory.user())
        url = f"/api/events/{event.id}"

        await api.patch(url, json={"starts_at": in_days(4)}, headers=as_user(organizer))
        await api.patch(url, json={"starts_at": in_days(5)}, headers=as_user(organizer))

    async def test_minor_changes_do_not_notify(
        self, api: AsyncClient, factory: Factory, published: FakePublisher
    ) -> None:
        """Изменение названия, описания и вместимости участников не тревожит."""
        organizer, event = await organizer_with_event(factory)
        await factory.registration(event, await factory.user())

        await api.patch(
            f"/api/events/{event.id}",
            json={"title": "Другое", "description": "Текст", "capacity": 9},
            headers=as_user(organizer),
        )

        assert published.messages == []

    async def test_same_value_does_not_notify(
        self, api: AsyncClient, factory: Factory, published: FakePublisher
    ) -> None:
        """Если значение не изменилось, уведомления нет."""
        organizer, event = await organizer_with_event(factory, location="Остановка")
        await factory.registration(event, await factory.user())

        await api.patch(
            f"/api/events/{event.id}", json={"location": "Остановка"}, headers=as_user(organizer)
        )

        assert published.messages == []

    async def test_shelter_change_notifies(
        self, api: AsyncClient, factory: Factory, published: FakePublisher
    ) -> None:
        """Смена приюта — это смена места, участники уведомляются."""
        organizer, event = await organizer_with_event(factory)
        await factory.registration(event, await factory.user())
        shelter = await factory.shelter()

        await api.patch(
            f"/api/events/{event.id}", json={"shelter_id": shelter.id}, headers=as_user(organizer)
        )

        assert published.messages[0].payload == {"title": event.title, "changed": ["shelter_id"]}


class TestEventCancel:
    """Отмена мероприятия."""

    async def test_owner_cancels_with_reason(self, api: AsyncClient, factory: Factory) -> None:
        """Организатор отменяет мероприятие с причиной."""
        organizer, event = await organizer_with_event(factory)

        response = await api.post(
            f"/api/events/{event.id}/cancel",
            json={"reason": "Плохая погода"},
            headers=as_user(organizer),
        )

        body = response.json()
        assert body["status"] == "cancelled"
        assert body["cancellation_reason"] == "Плохая погода"

    async def test_reason_is_required(self, api: AsyncClient, factory: Factory) -> None:
        """Без причины отменить нельзя."""
        organizer, event = await organizer_with_event(factory)

        no_reason = await api.post(
            f"/api/events/{event.id}/cancel", json={}, headers=as_user(organizer)
        )
        blank = await api.post(
            f"/api/events/{event.id}/cancel", json={"reason": "  "}, headers=as_user(organizer)
        )

        assert no_reason.status_code == 422
        assert blank.status_code == 422

    async def test_participants_are_notified_with_reason(
        self, api: AsyncClient, factory: Factory, published: FakePublisher
    ) -> None:
        """Участники получают уведомление об отмене с причиной."""
        organizer, event = await organizer_with_event(factory)
        participant = await factory.user()
        await factory.registration(event, participant)

        await api.post(
            f"/api/events/{event.id}/cancel", json={"reason": "Погода"}, headers=as_user(organizer)
        )

        (sent,) = published.messages
        assert sent.telegram_id == participant.telegram_id
        assert sent.type is NotificationType.EVENT_CANCELLED
        assert sent.payload is not None
        assert sent.payload["reason"] == "Погода"

    async def test_second_cancel_is_conflict(self, api: AsyncClient, factory: Factory) -> None:
        """Повторная отмена — 409."""
        organizer, event = await organizer_with_event(factory)
        url = f"/api/events/{event.id}/cancel"
        await api.post(url, json={"reason": "Погода"}, headers=as_user(organizer))

        response = await api.post(url, json={"reason": "Погода"}, headers=as_user(organizer))

        assert response.status_code == 409

    async def test_another_organizer_cannot_cancel(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Чужое мероприятие организатор отменить не может."""
        admin = await make_admin(factory)
        _, event = await organizer_with_event(factory, admin)
        other = await make_organizer(factory, admin)

        response = await api.post(
            f"/api/events/{event.id}/cancel", json={"reason": "Погода"}, headers=as_user(other)
        )

        assert response.status_code == 403

    async def test_admin_can_cancel_any_event(self, api: AsyncClient, factory: Factory) -> None:
        """Администратор отменяет любое мероприятие."""
        admin = await make_admin(factory)
        _, event = await organizer_with_event(factory, admin)

        response = await api.post(
            f"/api/events/{event.id}/cancel", json={"reason": "Погода"}, headers=as_user(admin)
        )

        assert response.status_code == 200


class TestEventComplete:
    """Завершение мероприятия."""

    async def test_started_event_can_be_completed(self, api: AsyncClient, factory: Factory) -> None:
        """Начавшееся мероприятие можно завершить."""
        organizer, event = await organizer_with_event(
            factory, starts_at=datetime.now(UTC) - timedelta(hours=2)
        )

        response = await api.post(f"/api/events/{event.id}/complete", headers=as_user(organizer))

        assert response.json()["status"] == "completed"

    async def test_future_event_cannot_be_completed(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Мероприятие, которое ещё не началось, завершить нельзя."""
        organizer, event = await organizer_with_event(factory)

        response = await api.post(f"/api/events/{event.id}/complete", headers=as_user(organizer))

        assert response.status_code == 409

    async def test_volunteer_cannot_complete(self, api: AsyncClient, factory: Factory) -> None:
        """Волонтёр не может завершать мероприятия."""
        _, event = await organizer_with_event(
            factory, starts_at=datetime.now(UTC) - timedelta(hours=2)
        )
        volunteer = await factory.user()

        response = await api.post(f"/api/events/{event.id}/complete", headers=as_user(volunteer))

        assert response.status_code == 403

    async def test_completed_event_cannot_be_completed_again(
        self, api: AsyncClient, factory: Factory
    ) -> None:
        """Повторное завершение — 409."""
        organizer, event = await organizer_with_event(
            factory, starts_at=datetime.now(UTC) - timedelta(hours=2)
        )
        url = f"/api/events/{event.id}/complete"
        await api.post(url, headers=as_user(organizer))

        response = await api.post(url, headers=as_user(organizer))

        assert response.status_code == 409
