from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, UnprocessableError
from app.database.models import Bonus, Event, Registration, Shelter, Tag, User
from app.database.models.enums import EventStatus, NotificationType, RegistrationStatus
from app.messaging.reminders import Reminders
from app.repositories.event.base import EventRepository
from app.repositories.shelters import ShelterRepository
from app.repositories.users import UserRepository
from app.schemas.event.base import EventCancel, EventCreate, EventFilters, EventUpdate
from app.schemas.pagination import Pagination
from app.services.access import Access
from app.services.notifications import NotificationService


@dataclass(frozen=True)
class EventDetails:
    """Мероприятие с тем, что зависит от запросившего: занятые места и доступ к чату."""

    event: Event
    occupied: int
    can_see_chat: bool


class EventService:
    """Сценарии работы с мероприятиями.

    Смотреть может любой пользователь. Создавать — организаторы и администраторы.
    Менять, отменять и завершать — организатор мероприятия или администратор.
    """

    NOTIFIED_FIELDS = ("starts_at", "ends_at", "location", "instructions")

    def __init__(self, session: AsyncSession) -> None:
        """Работает в переданной сессии."""
        self.__session = session
        self.__events = EventRepository(session)
        self.__shelters = ShelterRepository(session)
        self.__users = UserRepository(session)
        self.__notifications = NotificationService(session)

    async def search(
        self, filters: EventFilters, pagination: Pagination, current_user: User
    ) -> tuple[list[EventDetails], int]:
        """Список мероприятий; чат участников в списке не показывается."""
        events, total = await self.__events.search(filters, pagination)
        occupied = await self.__events.occupied([event.id for event in events])
        items = [EventDetails(event, occupied.get(event.id, 0), False) for event in events]

        return items, total

    async def get(self, event_id: int, current_user: User) -> EventDetails:
        """Карточка мероприятия."""
        event = await self.__require(event_id)
        details = await self.__details(event, current_user)

        return details

    async def create(self, data: EventCreate, current_user: User) -> EventDetails:
        """Создаёт мероприятие; организаторы и администраторы."""
        Access.require_staff(current_user)

        if data.starts_at <= datetime.now(UTC):
            raise UnprocessableError("Начало мероприятия должно быть в будущем")

        shelter = None

        if data.shelter_id is not None:
            shelter = await self.__shelters.get(data.shelter_id)

            if shelter is None:
                raise UnprocessableError("Приют не найден")

        is_approval_required = data.is_approval_required
        instructions = data.instructions

        if shelter is not None:
            if is_approval_required is None:
                is_approval_required = shelter.is_approval_required

            if instructions is None:
                instructions = shelter.instructions

        fields = data.model_dump(
            exclude={"shelter_id", "bonus_ids", "tag_ids", "is_approval_required", "instructions"}
        )
        event = Event(
            **fields,
            is_approval_required=bool(is_approval_required),
            instructions=instructions,
            created_by=current_user.id,
            shelter=shelter,
            creator=current_user,
            bonuses=await self.__bonuses(data.bonus_ids),
            tags=await self.__tags(data.tag_ids),
        )

        await self.__events.add(event)
        subscribers = await self.__users.subscriber_ids(exclude=[current_user.id])
        self.__notifications.add(
            subscribers,
            NotificationType.NEW_EVENT,
            event.id,
            {"title": event.title, "starts_at": event.starts_at.isoformat()},
        )
        await self.__notifications.commit()

        return EventDetails(event, 0, True)

    async def update(self, event_id: int, data: EventUpdate, current_user: User) -> EventDetails:
        """Изменяет мероприятие; участникам уходит уведомление, если изменились время или место."""
        event = await self.__require_manageable(event_id, current_user)
        fields = data.model_dump(exclude_unset=True)
        before = self.__snapshot(event)

        if "shelter_id" in fields:
            event.shelter = await self.__shelter(fields.pop("shelter_id"))

        if "bonus_ids" in fields:
            event.bonuses = await self.__bonuses(fields.pop("bonus_ids"))

        if "tag_ids" in fields:
            event.tags = await self.__tags(fields.pop("tag_ids"))

        for field, value in fields.items():
            setattr(event, field, value)

        await self.__check_consistency(event, "starts_at" in fields)

        after = self.__snapshot(event)
        changed = [name for name, value in before.items() if after[name] != value]

        await self.__events.flush()

        if changed:
            await self.__notify_changed(event, changed, "starts_at" in changed)

        await self.__notifications.commit()
        details = await self.__details(event, current_user)

        return details

    async def cancel(self, event_id: int, data: EventCancel, current_user: User) -> EventDetails:
        """Отменяет мероприятие; участникам уходит уведомление с причиной."""
        event = await self.__require_manageable(event_id, current_user)

        event.status = EventStatus.CANCELLED
        event.cancellation_reason = data.reason

        await self.__events.flush()

        recipients = await self.__events.participant_ids(event.id, Registration.NOTIFIABLE_STATUSES)
        self.__notifications.add(
            recipients,
            NotificationType.EVENT_CANCELLED,
            event.id,
            {"title": event.title, "starts_at": event.starts_at.isoformat(), "reason": data.reason},
        )
        await self.__notifications.commit()
        details = await self.__details(event, current_user)

        return details

    async def complete(self, event_id: int, current_user: User) -> EventDetails:
        """Завершает мероприятие; только после его начала."""
        event = await self.__require_manageable(event_id, current_user)

        if event.starts_at > datetime.now(UTC):
            raise ConflictError("Мероприятие ещё не началось")

        event.status = EventStatus.COMPLETED

        await self.__events.flush()
        await self.__notifications.commit()
        details = await self.__details(event, current_user)

        return details

    async def __require(self, event_id: int) -> Event:
        """Возвращает мероприятие или выбрасывает NotFoundError."""
        event = await self.__events.get(event_id)

        if event is None:
            raise NotFoundError("Мероприятие не найдено")

        return event

    async def __require_manageable(self, event_id: int, current_user: User) -> Event:
        """Мероприятие, которое пользователь вправе менять: его организатор или администратор."""
        event = await self.__require(event_id)
        is_owner = Access.is_staff(current_user) and event.created_by == current_user.id

        if not (Access.is_admin(current_user) or is_owner):
            raise ForbiddenError("Менять мероприятие может его организатор или администратор")

        if event.status is not EventStatus.PLANNED:
            raise ConflictError("Отменённое или завершённое мероприятие менять нельзя")

        return event

    async def __details(self, event: Event, current_user: User) -> EventDetails:
        """Занятые места и право видеть чат: персоналу и подтверждённым участникам."""
        occupied = await self.__events.occupied([event.id])
        can_see_chat = Access.is_staff(current_user) or await self.__events.has_registration(
            event.id, current_user.id, Registration.CONFIRMED_STATUSES
        )

        return EventDetails(event, occupied.get(event.id, 0), can_see_chat)

    async def __shelter(self, shelter_id: int | None) -> Shelter | None:
        """Приют по ID или None; несуществующий приют — ошибка запроса."""
        if shelter_id is None:
            return None

        shelter = await self.__shelters.get(shelter_id)

        if shelter is None:
            raise UnprocessableError("Приют не найден")

        return shelter

    async def __bonuses(self, bonus_ids: list[int]) -> list[Bonus]:
        """Бонусы по ID; все должны существовать."""
        bonuses = await self.__events.find_bonuses(bonus_ids)

        if len(bonuses) != len(set(bonus_ids)):
            raise UnprocessableError("Бонус не найден")

        return bonuses

    async def __tags(self, tag_ids: list[int]) -> list[Tag]:
        """Теги по ID; все должны существовать."""
        tags = await self.__events.find_tags(tag_ids)

        if len(tags) != len(set(tag_ids)):
            raise UnprocessableError("Тег не найден")

        return tags

    async def __check_consistency(self, event: Event, is_start_changed: bool) -> None:
        """Проверки, которые зависят от нескольких полей сразу."""
        if is_start_changed and event.starts_at <= datetime.now(UTC):
            raise UnprocessableError("Начало мероприятия должно быть в будущем")

        if event.ends_at is not None and event.ends_at <= event.starts_at:
            raise UnprocessableError("Окончание должно быть позже начала")

        if event.location is None and event.shelter is None:
            raise UnprocessableError("Укажите приют или место встречи")

        occupied = await self.__events.occupied([event.id])

        if event.capacity < occupied.get(event.id, 0):
            raise ConflictError("Нельзя уменьшить вместимость ниже числа занятых мест")

    async def __notify_changed(
        self, event: Event, changed: list[str], is_start_moved: bool
    ) -> None:
        """Сообщает участникам об изменении времени, места или инструкции.

        Если сдвинулось начало, подтверждённым участникам заново назначается напоминание:
        оно заменит прежнее, ещё не отправленное.
        """
        recipients = await self.__events.participant_ids(event.id, Registration.NOTIFIABLE_STATUSES)
        self.__notifications.add(
            recipients,
            NotificationType.EVENT_CHANGED,
            event.id,
            {"title": event.title, "changed": changed},
        )

        send_at = Reminders.send_at(event.starts_at)

        if is_start_moved and send_at is not None:
            confirmed = await self.__events.participant_ids(
                event.id, {RegistrationStatus.REGISTERED}
            )
            self.__notifications.add(
                confirmed,
                NotificationType.REMINDER,
                event.id,
                {"title": event.title, "starts_at": event.starts_at.isoformat()},
                send_at=send_at,
                key=Reminders.key(event.id),
            )

    def __snapshot(self, event: Event) -> dict[str, Any]:
        """Значения полей, об изменении которых нужно знать."""
        values = {name: getattr(event, name) for name in self.NOTIFIED_FIELDS}
        values["shelter_id"] = event.shelter.id if event.shelter else None

        return values
