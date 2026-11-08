import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Broadcast
from app.database.models.enums import BroadcastAudience, BroadcastStatus
from tests.app.database.conftest import Rejected
from tests.app.database.factory import Factory

pytestmark = pytest.mark.integration


class TestBroadcastInDatabase:
    """Таблица broadcasts на настоящей БД."""

    async def test_default_status_is_draft(self, session: AsyncSession, factory: Factory) -> None:
        """Новая рассылка — черновик."""
        author = await factory.user()
        broadcast = Broadcast(author_id=author.id, text="Привет", audience=BroadcastAudience.ALL)
        session.add(broadcast)
        await session.flush()

        assert broadcast.status is BroadcastStatus.DRAFT

    async def test_event_participants_require_event(
        self, session: AsyncSession, factory: Factory, rejected: Rejected
    ) -> None:
        """Рассылка участникам мероприятия без мероприятия отклоняется."""
        author = await factory.user()

        async with rejected("ck_broadcasts_event_matches_audience"):
            session.add(
                Broadcast(
                    author_id=author.id,
                    text="Привет",
                    audience=BroadcastAudience.EVENT_PARTICIPANTS,
                )
            )

    async def test_other_audience_forbids_event(
        self, session: AsyncSession, factory: Factory, rejected: Rejected
    ) -> None:
        """Рассылка всем с привязкой к мероприятию отклоняется."""
        author = await factory.user()
        event = await factory.event()

        async with rejected("ck_broadcasts_event_matches_audience"):
            session.add(
                Broadcast(
                    author_id=author.id,
                    text="Привет",
                    audience=BroadcastAudience.ALL,
                    event_id=event.id,
                )
            )

    async def test_event_participants_with_event_is_accepted(
        self, session: AsyncSession, factory: Factory
    ) -> None:
        """Рассылка участникам мероприятия с указанным мероприятием принимается."""
        author = await factory.user()
        event = await factory.event()
        broadcast = Broadcast(
            author_id=author.id,
            text="Привет",
            audience=BroadcastAudience.EVENT_PARTICIPANTS,
            event_id=event.id,
        )
        session.add(broadcast)
        await session.flush()

        assert broadcast.event_id == event.id

    async def test_author_with_broadcasts_cannot_be_deleted(
        self, session: AsyncSession, factory: Factory, rejected: Rejected
    ) -> None:
        """Автора рассылок удалить нельзя."""
        author = await factory.user()
        session.add(Broadcast(author_id=author.id, text="Привет", audience=BroadcastAudience.ALL))
        await session.flush()

        async with rejected("fk_broadcasts_author_id_users"):
            await session.delete(author)
