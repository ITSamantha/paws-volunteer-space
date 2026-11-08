from datetime import timedelta

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Event, Shelter
from app.database.models.enums import EventStatus
from tests.app.conftest import Rejected
from tests.app.database.factory import Factory

pytestmark = pytest.mark.integration


class TestEventInDatabase:
    """Таблица events на настоящей БД."""

    async def test_defaults_are_applied(self, factory: Factory) -> None:
        """Новое мероприятие запланировано, одобрение записей не требуется."""
        event = await factory.event()

        assert event.status is EventStatus.PLANNED
        assert event.is_approval_required is False

    @pytest.mark.parametrize("capacity", [0, -1])
    async def test_non_positive_capacity_is_rejected(
        self, factory: Factory, rejected: Rejected, capacity: int
    ) -> None:
        """Лимит участников должен быть положительным."""
        async with rejected("ck_events_capacity_positive"):
            await factory.event(capacity=capacity)

    async def test_end_before_start_is_rejected(self, factory: Factory, rejected: Rejected) -> None:
        """Окончание раньше или одновременно с началом отклоняется."""
        event = await factory.event()

        async with rejected("ck_events_ends_after_start"):
            await factory.event(starts_at=event.starts_at, ends_at=event.starts_at)

    async def test_end_may_be_omitted(self, factory: Factory) -> None:
        """Окончание необязательно."""
        event = await factory.event(ends_at=None)

        assert event.ends_at is None

    async def test_end_after_start_is_accepted(self, factory: Factory) -> None:
        """Окончание позже начала принимается."""
        event = await factory.event()
        later = await factory.event(
            starts_at=event.starts_at, ends_at=event.starts_at + timedelta(hours=3)
        )

        assert later.ends_at is not None

    async def test_place_is_required(self, factory: Factory, rejected: Rejected) -> None:
        """Без собственного места и без приюта мероприятие не создать."""
        async with rejected("ck_events_has_place"):
            await factory.event(location=None, shelter_id=None)

    async def test_shelter_alone_is_enough_for_place(self, factory: Factory) -> None:
        """Достаточно приюта: место встречи берётся из его адреса."""
        shelter = await factory.shelter()

        event = await factory.event(location=None, shelter_id=shelter.id)

        assert event.shelter_id == shelter.id

    async def test_cancelled_event_requires_reason(
        self, factory: Factory, rejected: Rejected
    ) -> None:
        """Отменить мероприятие без причины нельзя."""
        async with rejected("ck_events_cancelled_requires_reason"):
            await factory.event(status=EventStatus.CANCELLED)

    async def test_cancelled_event_with_reason_is_accepted(self, factory: Factory) -> None:
        """Отмена с причиной принимается."""
        event = await factory.event(status=EventStatus.CANCELLED, cancellation_reason="Погода")

        assert event.status is EventStatus.CANCELLED

    async def test_shelter_cannot_be_removed_when_event_depends_on_it(
        self, session: AsyncSession, factory: Factory, rejected: Rejected
    ) -> None:
        """Приют без собственного места встречи у мероприятия удалить нельзя."""
        shelter = await factory.shelter()
        await factory.event(location=None, shelter_id=shelter.id)

        async with rejected("ck_events_has_place"):
            await session.execute(delete(Shelter).where(Shelter.id == shelter.id))

    async def test_shelter_removal_clears_reference(
        self, session: AsyncSession, factory: Factory
    ) -> None:
        """Если у мероприятия есть своё место, при удалении приюта ссылка обнуляется."""
        shelter = await factory.shelter()
        event = await factory.event(shelter_id=shelter.id)

        await session.execute(delete(Shelter).where(Shelter.id == shelter.id))
        await session.refresh(event)

        assert event.shelter_id is None

    async def test_organizer_with_events_cannot_be_deleted(
        self, session: AsyncSession, factory: Factory, rejected: Rejected
    ) -> None:
        """Организатора, создавшего мероприятия, удалить нельзя."""
        organizer = await factory.user()
        await factory.event(organizer=organizer)

        async with rejected("fk_events_created_by_users"):
            await session.delete(organizer)

    async def test_event_is_persisted(self, session: AsyncSession, factory: Factory) -> None:
        """Мероприятие сохраняется и читается обратно."""
        event = await factory.event(title="Прогулка с собаками")

        assert await session.get(Event, event.id) is event
