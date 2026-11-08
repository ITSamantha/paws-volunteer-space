from datetime import UTC, datetime

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Event, Registration
from app.database.models.enums import RegistrationStatus
from tests.app.conftest import Rejected
from tests.app.database.factory import Factory

pytestmark = pytest.mark.integration


class TestRegistrationInDatabase:
    """Таблица registrations на настоящей БД."""

    async def test_default_status_is_registered(self, factory: Factory) -> None:
        """Запись по умолчанию подтверждена."""
        event = await factory.event()
        registration = await factory.registration(event, await factory.user())

        assert registration.status is RegistrationStatus.REGISTERED

    async def test_user_cannot_register_twice(
        self, session: AsyncSession, factory: Factory, rejected: Rejected
    ) -> None:
        """Один человек не может записаться на одно мероприятие дважды."""
        event = await factory.event()
        user = await factory.user()
        await factory.registration(event, user)

        async with rejected("uq_registrations_event_id_user_id"):
            session.add(Registration(event_id=event.id, user_id=user.id))

    async def test_event_with_registrations_cannot_be_deleted(
        self, session: AsyncSession, factory: Factory, rejected: Rejected
    ) -> None:
        """Мероприятие с записями удалить нельзя."""
        event = await factory.event()
        await factory.registration(event, await factory.user())

        async with rejected("fk_registrations_event_id_events"):
            await session.execute(delete(Event).where(Event.id == event.id))


class TestCancellation:
    """Отмена записи."""

    async def test_cancellation_requires_reason(self, factory: Factory, rejected: Rejected) -> None:
        """Отменить запись без причины нельзя."""
        event = await factory.event()
        user = await factory.user()

        async with rejected("ck_registrations_cancelled_requires_reason"):
            await factory.registration(
                event, user, status=RegistrationStatus.CANCELLED, cancelled_at=datetime.now(UTC)
            )

    async def test_blank_reason_is_rejected(self, factory: Factory, rejected: Rejected) -> None:
        """Причина из одних пробелов не считается."""
        event = await factory.event()
        user = await factory.user()

        async with rejected("ck_registrations_cancelled_requires_reason"):
            await factory.registration(
                event,
                user,
                status=RegistrationStatus.CANCELLED,
                cancelled_at=datetime.now(UTC),
                cancellation_reason="  ",
            )

    async def test_cancellation_requires_time(self, factory: Factory, rejected: Rejected) -> None:
        """У отменённой записи должно быть время отмены."""
        event = await factory.event()
        user = await factory.user()

        async with rejected("ck_registrations_cancelled_at_matches_status"):
            await factory.registration(
                event,
                user,
                status=RegistrationStatus.CANCELLED,
                cancellation_reason="Заболел",
            )

    async def test_time_without_cancellation_is_rejected(
        self, factory: Factory, rejected: Rejected
    ) -> None:
        """Время отмены у неотменённой записи не допускается."""
        event = await factory.event()
        user = await factory.user()

        async with rejected("ck_registrations_cancelled_at_matches_status"):
            await factory.registration(event, user, cancelled_at=datetime.now(UTC))

    async def test_complete_cancellation_is_accepted(self, factory: Factory) -> None:
        """Отмена с причиной и временем принимается."""
        event = await factory.event()
        user = await factory.user()

        registration = await factory.registration(
            event,
            user,
            status=RegistrationStatus.CANCELLED,
            cancelled_at=datetime.now(UTC),
            cancellation_reason="Заболел",
        )

        assert registration.status is RegistrationStatus.CANCELLED

    async def test_registration_can_be_restored_after_cancellation(
        self, session: AsyncSession, factory: Factory
    ) -> None:
        """После отмены запись возвращается в работу, если сбросить поля отмены."""
        event = await factory.event()
        user = await factory.user()
        registration = await factory.registration(
            event,
            user,
            status=RegistrationStatus.CANCELLED,
            cancelled_at=datetime.now(UTC),
            cancellation_reason="Заболел",
        )

        registration.status = RegistrationStatus.REGISTERED
        registration.cancelled_at = None
        registration.cancellation_reason = None
        await session.flush()

        assert registration.status is RegistrationStatus.REGISTERED


class TestDecision:
    """Решение организатора по заявке."""

    async def test_responsible_organizer_can_decide(self, factory: Factory) -> None:
        """Решение принимает организатор, создавший мероприятие."""
        organizer = await factory.user()
        event = await factory.event(organizer=organizer, is_approval_required=True)
        registration = await factory.registration(
            event,
            await factory.user(),
            decided_by=organizer.id,
            decided_at=datetime.now(UTC),
        )

        assert registration.decided_by == organizer.id

    async def test_other_organizer_cannot_decide(
        self, factory: Factory, rejected: Rejected
    ) -> None:
        """Другой организатор не может принять решение по чужому мероприятию."""
        event = await factory.event()
        stranger = await factory.user()
        applicant = await factory.user()

        async with rejected("только ответственный организатор"):
            await factory.registration(
                event, applicant, decided_by=stranger.id, decided_at=datetime.now(UTC)
            )

    async def test_decision_author_must_come_with_time(
        self, factory: Factory, rejected: Rejected
    ) -> None:
        """Автор решения и время решения заполняются вместе."""
        organizer = await factory.user()
        event = await factory.event(organizer=organizer)

        async with rejected("ck_registrations_decision_author_matches_time"):
            await factory.registration(event, await factory.user(), decided_by=organizer.id)

    async def test_rejection_requires_author_and_comment(
        self, factory: Factory, rejected: Rejected
    ) -> None:
        """Отклонить заявку без автора и комментария нельзя."""
        event = await factory.event()

        async with rejected("ck_registrations_rejected_requires_decision"):
            await factory.registration(
                event, await factory.user(), status=RegistrationStatus.REJECTED
            )

    async def test_complete_rejection_is_accepted(self, factory: Factory) -> None:
        """Отклонение с автором, временем и комментарием принимается."""
        organizer = await factory.user()
        event = await factory.event(organizer=organizer, is_approval_required=True)

        registration = await factory.registration(
            event,
            await factory.user(),
            status=RegistrationStatus.REJECTED,
            decided_by=organizer.id,
            decided_at=datetime.now(UTC),
            decision_comment="Нет допуска в приют",
        )

        assert registration.status is RegistrationStatus.REJECTED

    async def test_organizer_with_decisions_cannot_be_deleted(
        self, session: AsyncSession, factory: Factory, rejected: Rejected
    ) -> None:
        """Организатора, принимавшего решения, удалить нельзя."""
        organizer = await factory.user()
        event = await factory.event(organizer=organizer)
        await factory.registration(
            event, await factory.user(), decided_by=organizer.id, decided_at=datetime.now(UTC)
        )

        async with rejected("fk_"):
            await session.delete(organizer)
