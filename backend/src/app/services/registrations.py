from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.database.models import Event, Registration, User
from app.database.models.enums import EventStatus, NotificationType, RegistrationStatus
from app.messaging.reminders import Reminders
from app.repositories.event.base import EventRepository
from app.repositories.registrations import RegistrationRepository
from app.schemas.pagination import Pagination
from app.schemas.registrations import RegistrationCancel, RegistrationReject
from app.services.access import Access
from app.services.notifications import NotificationService


@dataclass(frozen=True)
class OwnRegistration:
    """Своя запись вместе с мероприятием и числом занятых мест."""

    registration: Registration
    event: Event
    occupied: int


class RegistrationService:
    """Сценарии записи на мероприятия.

    Места считаются под блокировкой строки мероприятия, поэтому при одновременных записях
    лимит не превышается. Решения по заявкам принимает только ответственный организатор.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Работает в переданной сессии."""
        self.__session = session
        self.__events = EventRepository(session)
        self.__registrations = RegistrationRepository(session)
        self.__notifications = NotificationService(session)

    async def register(self, event_id: int, current_user: User) -> Registration:
        """Записывает пользователя; статус зависит от свободных мест и режима одобрения."""
        await self.__events.lock(event_id)
        event = await self.__require_open(event_id)
        registration = await self.__registrations.get(event.id, current_user.id)

        if registration is not None:
            self.__check_can_register_again(registration)

        status = await self.__status_for_new(event)

        if registration is None:
            registration = Registration(event_id=event.id, user_id=current_user.id, status=status)
            await self.__registrations.add(registration)
        else:
            self.__reopen(registration, status)
            await self.__registrations.flush()

        self.__notify_registered(event, registration, current_user)
        await self.__notifications.commit()

        reloaded = await self.__reload(event.id, current_user.id)

        return reloaded

    async def claim(self, event_id: int, current_user: User) -> Registration:
        """Занимает освободившееся место: для тех, кто в листе ожидания."""
        await self.__events.lock(event_id)
        event = await self.__require_open(event_id)
        registration = await self.__require_own(event.id, current_user.id)

        if registration.status is not RegistrationStatus.WAITLISTED:
            raise ConflictError("Вы не в листе ожидания")

        status = await self.__status_for_new(event)

        if status is RegistrationStatus.WAITLISTED:
            raise ConflictError("Свободных мест пока нет")

        registration.status = status
        await self.__registrations.flush()
        self.__notify_registered(event, registration, current_user)
        await self.__notifications.commit()

        reloaded = await self.__reload(event.id, current_user.id)

        return reloaded

    async def cancel(
        self, event_id: int, data: RegistrationCancel, current_user: User
    ) -> Registration:
        """Отменяет свою запись; освободившееся место предлагается листу ожидания."""
        await self.__events.lock(event_id)
        event = await self.__require_open(event_id)
        registration = await self.__require_own(event.id, current_user.id)

        if registration.status not in Registration.CANCELLABLE_STATUSES:
            raise ConflictError("Эту запись отменить нельзя")

        was_holding_place = registration.status in Registration.OCCUPYING_STATUSES

        registration.status = RegistrationStatus.CANCELLED
        registration.cancelled_at = datetime.now(UTC)
        registration.cancellation_reason = data.reason
        await self.__registrations.flush()

        self.__notify(
            [event.created_by] if event.created_by != current_user.id else [],
            NotificationType.ORGANIZER_CANCELLATION,
            event,
            registration,
            {"title": event.title, "full_name": current_user.full_name, "reason": data.reason},
        )
        self.__notify(
            [current_user.id],
            NotificationType.REGISTRATION_CANCELLED,
            event,
            registration,
            {"title": event.title},
        )

        if was_holding_place:
            await self.__offer_free_place(event, registration)

        await self.__notifications.commit()

        reloaded = await self.__reload(event.id, current_user.id)

        return reloaded

    async def approve(
        self, event_id: int, registration_id: int, current_user: User
    ) -> Registration:
        """Одобряет заявку; только ответственный организатор."""
        event, registration = await self.__pending_for_decision(
            event_id, registration_id, current_user
        )

        registration.status = RegistrationStatus.REGISTERED
        self.__decide(registration, current_user, None)
        await self.__registrations.flush()

        self.__notify(
            [registration.user_id],
            NotificationType.REGISTRATION_APPROVED,
            event,
            registration,
            {"title": event.title, "starts_at": event.starts_at.isoformat()},
        )
        self.__remind(event, registration.user_id)
        await self.__notifications.commit()

        return registration

    async def reject(
        self, event_id: int, registration_id: int, data: RegistrationReject, current_user: User
    ) -> Registration:
        """Отклоняет заявку с причиной; только ответственный организатор."""
        event, registration = await self.__pending_for_decision(
            event_id, registration_id, current_user
        )

        registration.status = RegistrationStatus.REJECTED
        self.__decide(registration, current_user, data.comment)
        await self.__registrations.flush()

        self.__notify(
            [registration.user_id],
            NotificationType.REGISTRATION_REJECTED,
            event,
            registration,
            {"title": event.title, "comment": data.comment},
        )
        await self.__offer_free_place(event, registration)
        await self.__notifications.commit()

        return registration

    async def mark_attendance(
        self, event_id: int, registration_id: int, attended: bool, current_user: User
    ) -> Registration:
        """Отмечает, пришёл ли волонтёр; организатор мероприятия или администратор."""
        event = await self.__require_event(event_id)
        self.__require_manager(event, current_user)

        if event.status is EventStatus.CANCELLED:
            raise ConflictError("Мероприятие отменено")

        if event.starts_at > datetime.now(UTC):
            raise ConflictError("Мероприятие ещё не началось")

        registration = await self.__require_registration(event.id, registration_id)

        if registration.status not in Registration.ATTENDANCE_STATUSES:
            raise ConflictError("Посещение можно отметить только у записанных участников")

        registration.status = RegistrationStatus.ATTENDED if attended else RegistrationStatus.ABSENT
        await self.__registrations.flush()
        await self.__notifications.commit()

        return registration

    async def participants(
        self,
        event_id: int,
        statuses: list[RegistrationStatus] | None,
        pagination: Pagination,
        current_user: User,
    ) -> tuple[list[Registration], int]:
        """Список записавшихся; организаторы и администраторы."""
        Access.require_staff(current_user)
        event = await self.__require_event(event_id)

        page = await self.__registrations.search_by_event(event.id, statuses, pagination)

        return page

    async def own(self, event_id: int, current_user: User) -> Registration:
        """Своя запись на мероприятие."""
        await self.__require_event(event_id)
        registration = await self.__require_own(event_id, current_user.id)

        return registration

    async def own_list(
        self,
        statuses: list[RegistrationStatus] | None,
        pagination: Pagination,
        current_user: User,
    ) -> tuple[list[OwnRegistration], int]:
        """Все свои записи вместе с мероприятиями, новые первыми."""
        registrations, total = await self.__registrations.search_by_user(
            current_user.id, statuses, pagination
        )
        events = await self.__events.get_many([item.event_id for item in registrations])
        by_id = {event.id: event for event in events}
        occupied = await self.__events.occupied(list(by_id))
        items = [
            OwnRegistration(item, by_id[item.event_id], occupied.get(item.event_id, 0))
            for item in registrations
        ]

        return items, total

    async def __require_event(self, event_id: int) -> Event:
        """Мероприятие или NotFoundError."""
        event = await self.__events.get(event_id)

        if event is None:
            raise NotFoundError("Мероприятие не найдено")

        return event

    async def __require_open(self, event_id: int) -> Event:
        """Мероприятие, на которое ещё можно записываться и отменять запись."""
        event = await self.__require_event(event_id)

        if event.status is not EventStatus.PLANNED:
            raise ConflictError("Мероприятие отменено или завершено")

        if event.starts_at <= datetime.now(UTC):
            raise ConflictError("Мероприятие уже началось")

        return event

    async def __require_own(self, event_id: int, user_id: int) -> Registration:
        """Запись пользователя или NotFoundError."""
        registration = await self.__registrations.get(event_id, user_id)

        if registration is None:
            raise NotFoundError("Вы не записаны на это мероприятие")

        return registration

    async def __require_registration(self, event_id: int, registration_id: int) -> Registration:
        """Запись по ID или NotFoundError."""
        registration = await self.__registrations.get_by_id(event_id, registration_id)

        if registration is None:
            raise NotFoundError("Запись не найдена")

        return registration

    async def __reload(self, event_id: int, user_id: int) -> Registration:
        """Запись в актуальном виде после коммита."""
        registration = await self.__require_own(event_id, user_id)

        return registration

    async def __pending_for_decision(
        self, event_id: int, registration_id: int, current_user: User
    ) -> tuple[Event, Registration]:
        """Заявка, по которой пользователь вправе принять решение."""
        event = await self.__require_event(event_id)

        if event.created_by != current_user.id:
            raise ForbiddenError("Решение по заявке принимает ответственный организатор")

        if event.status is not EventStatus.PLANNED:
            raise ConflictError("Мероприятие отменено или завершено")

        registration = await self.__require_registration(event.id, registration_id)

        if registration.status is not RegistrationStatus.PENDING:
            raise ConflictError("Заявка не ждёт решения")

        return event, registration

    async def __status_for_new(self, event: Event) -> RegistrationStatus:
        """Статус новой записи: есть место — запись или заявка, нет — лист ожидания."""
        occupied = await self.__events.occupied([event.id])

        if occupied.get(event.id, 0) >= event.capacity:
            return RegistrationStatus.WAITLISTED

        if event.is_approval_required:
            return RegistrationStatus.PENDING

        return RegistrationStatus.REGISTERED

    async def __offer_free_place(self, event: Event, registration: Registration) -> None:
        """Сообщает листу ожидания об освободившемся месте."""
        waiting = await self.__events.participant_ids(event.id, {RegistrationStatus.WAITLISTED})

        self.__notify(
            waiting,
            NotificationType.SPOT_FREED,
            event,
            registration,
            {"title": event.title, "starts_at": event.starts_at.isoformat()},
        )

    def __notify_registered(
        self, event: Event, registration: Registration, current_user: User
    ) -> None:
        """События после записи, заявки или попадания в лист ожидания."""
        title = {"title": event.title, "starts_at": event.starts_at.isoformat()}
        organizer = [event.created_by] if event.created_by != current_user.id else []
        about_user = {"title": event.title, "full_name": current_user.full_name}

        match registration.status:
            case RegistrationStatus.REGISTERED:
                user_type = NotificationType.REGISTRATION_CONFIRMED
                organizer_type: NotificationType | None = (
                    NotificationType.ORGANIZER_NEW_REGISTRATION
                )
            case RegistrationStatus.PENDING:
                user_type = NotificationType.REGISTRATION_PENDING
                organizer_type = NotificationType.ORGANIZER_APPROVAL_REQUESTED
            case _:
                user_type = NotificationType.REGISTRATION_WAITLISTED
                organizer_type = None

        self.__notify([current_user.id], user_type, event, registration, title)

        if organizer_type is not None:
            self.__notify(organizer, organizer_type, event, registration, about_user)

        if registration.status is RegistrationStatus.REGISTERED:
            self.__remind(event, current_user.id)

    def __notify(
        self,
        user_ids: list[int],
        notification_type: NotificationType,
        event: Event,
        registration: Registration,
        payload: dict[str, Any],
    ) -> None:
        """Событие без особого времени: отправить сразу."""
        data = {**payload, "registration_id": registration.id}

        self.__notifications.add(user_ids, notification_type, event.id, data)

    def __remind(self, event: Event, user_id: int) -> None:
        """Напоминание о мероприятии; время рассчитывается заранее, отправляет бот."""
        send_at = Reminders.send_at(event.starts_at)

        if send_at is None:
            return

        self.__notifications.add(
            [user_id],
            NotificationType.REMINDER,
            event.id,
            {"title": event.title, "starts_at": event.starts_at.isoformat()},
            send_at=send_at,
            key=Reminders.key(event.id),
        )

    @staticmethod
    def __check_can_register_again(registration: Registration) -> None:
        """Повторно записаться можно только после отмены своей записи."""
        match registration.status:
            case RegistrationStatus.CANCELLED:
                return
            case RegistrationStatus.WAITLISTED:
                raise ConflictError("Вы уже в листе ожидания")
            case RegistrationStatus.REJECTED:
                raise ConflictError("Организатор отклонил вашу заявку")
            case _:
                raise ConflictError("Вы уже записаны на это мероприятие")

    @staticmethod
    def __reopen(registration: Registration, status: RegistrationStatus) -> None:
        """Возвращает отменённую запись в работу: прежняя отмена и решение сбрасываются."""
        registration.status = status
        registration.cancelled_at = None
        registration.cancellation_reason = None
        registration.decided_by = None
        registration.decided_at = None
        registration.decision_comment = None

    @staticmethod
    def __decide(registration: Registration, current_user: User, comment: str | None) -> None:
        """Фиксирует решение организатора."""
        registration.decided_by = current_user.id
        registration.decided_at = datetime.now(UTC)
        registration.decision_comment = comment

    @staticmethod
    def __require_manager(event: Event, current_user: User) -> None:
        """Организатор мероприятия или администратор."""
        is_owner = Access.is_staff(current_user) and event.created_by == current_user.id

        if not (Access.is_admin(current_user) or is_owner):
            raise ForbiddenError("Доступно организатору мероприятия и администратору")
