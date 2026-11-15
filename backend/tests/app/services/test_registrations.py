import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)

from app.core.exceptions import ConflictError
from app.database.models import Event, Registration, User
from app.database.models.enums import RegistrationStatus
from app.services.registrations import RegistrationService

pytestmark = pytest.mark.integration


async def create_event(
    committed_sessions: async_sessionmaker[AsyncSession], capacity: int, volunteers: int
) -> tuple[int, list[int]]:
    async with committed_sessions() as session:
        organizer = User(telegram_id=1, phone="+79990000000")
        session.add(organizer)
        await session.flush()
        event = Event(
            title="Выезд",
            starts_at=datetime.now(UTC) + timedelta(days=1),
            location="Остановка",
            capacity=capacity,
            created_by=organizer.id,
        )
        users = [
            User(telegram_id=100 + number, phone="+79990000000") for number in range(volunteers)
        ]
        session.add_all([event, *users])
        await session.commit()

        return event.id, [user.id for user in users]


async def register(
    committed_sessions: async_sessionmaker[AsyncSession], event_id: int, user_id: int
) -> None:
    async with committed_sessions() as session:
        user = await session.get(User, user_id)
        assert user is not None
        await session.refresh(user, ["roles"])

        await RegistrationService(session).register(event_id, user)


async def statuses(
    committed_sessions: async_sessionmaker[AsyncSession], event_id: int
) -> dict[str, int]:
    async with committed_sessions() as session:
        rows = await session.execute(
            select(Registration.status, func.count())
            .where(Registration.event_id == event_id)
            .group_by(Registration.status)
        )

        return {status.value: count for status, count in rows}


class TestConcurrentRegistration:
    """Одновременные записи не превышают лимит."""

    async def test_capacity_is_never_exceeded(
        self, committed_sessions: async_sessionmaker[AsyncSession]
    ) -> None:
        """Десять человек записываются одновременно на три места: занято ровно три."""
        event_id, user_ids = await create_event(committed_sessions, capacity=3, volunteers=10)

        await asyncio.gather(
            *(register(committed_sessions, event_id, user_id) for user_id in user_ids)
        )

        assert await statuses(committed_sessions, event_id) == {"registered": 3, "waitlisted": 7}

    async def test_only_one_user_takes_a_freed_place(
        self, committed_sessions: async_sessionmaker[AsyncSession]
    ) -> None:
        """Пятеро одновременно занимают одно освободившееся место: удаётся только одному."""
        event_id, user_ids = await create_event(committed_sessions, capacity=1, volunteers=5)
        async with committed_sessions() as session:
            for user_id in user_ids:
                session.add(
                    Registration(
                        event_id=event_id, user_id=user_id, status=RegistrationStatus.WAITLISTED
                    )
                )
            await session.commit()

        async def claim(user_id: int) -> bool:
            async with committed_sessions() as session:
                user = await session.get(User, user_id)
                assert user is not None
                await session.refresh(user, ["roles"])

                try:
                    await RegistrationService(session).claim(event_id, user)
                except ConflictError:
                    return False

                return True

        results = await asyncio.gather(*(claim(user_id) for user_id in user_ids))

        assert results.count(True) == 1
        assert await statuses(committed_sessions, event_id) == {"registered": 1, "waitlisted": 4}
