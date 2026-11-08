import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Bonus, Event, EventBonus, EventTag, Tag
from tests.app.database.conftest import Rejected
from tests.app.database.factory import Factory

pytestmark = pytest.mark.integration


@pytest.fixture(params=[Bonus, Tag], ids=["bonus", "tag"])
def dictionary(request: pytest.FixtureRequest) -> type[Bonus] | type[Tag]:
    model: type[Bonus] | type[Tag] = request.param
    return model


class TestDictionaryTitles:
    """Названия в справочниках бонусов и тегов."""

    async def test_titles_are_unique_ignoring_case(
        self, session: AsyncSession, rejected: Rejected, dictionary: type[Bonus] | type[Tag]
    ) -> None:
        """«Собаки» и «собаки» считаются одним значением."""
        session.add(dictionary(title="Собаки"))
        await session.flush()

        async with rejected("title_lower"):
            session.add(dictionary(title="собаки"))

    @pytest.mark.parametrize("title", ["", "   ", " Кошки", "Кошки "])
    async def test_untrimmed_title_is_rejected(
        self,
        session: AsyncSession,
        rejected: Rejected,
        dictionary: type[Bonus] | type[Tag],
        title: str,
    ) -> None:
        """Пустое название или пробелы по краям отклоняются."""
        async with rejected("title_trimmed"):
            session.add(dictionary(title=title))

    async def test_author_is_optional(
        self, session: AsyncSession, dictionary: type[Bonus] | type[Tag]
    ) -> None:
        """У значения из начального справочника нет автора."""
        item = dictionary(title="Выезд-тест")
        session.add(item)
        await session.flush()

        assert item.created_by is None

    async def test_author_with_items_cannot_be_deleted(
        self,
        session: AsyncSession,
        factory: Factory,
        rejected: Rejected,
        dictionary: type[Bonus] | type[Tag],
    ) -> None:
        """Пользователя, добавившего значение, удалить нельзя."""
        author = await factory.user()
        session.add(dictionary(title="Своё", created_by=author.id))
        await session.flush()

        async with rejected("fk_"):
            await session.delete(author)


class TestEventLinks:
    """Привязка бонусов и тегов к мероприятию."""

    async def test_links_are_deleted_with_event(
        self, session: AsyncSession, factory: Factory
    ) -> None:
        """При удалении мероприятия его бонусы и теги отвязываются."""
        event = await factory.event()
        bonus, tag = Bonus(title="ПГАС-тест"), Tag(title="Выезд-тест")
        session.add_all([bonus, tag])
        await session.flush()
        session.add_all(
            [
                EventBonus(event_id=event.id, bonus_id=bonus.id),
                EventTag(event_id=event.id, tag_id=tag.id),
            ]
        )
        await session.flush()

        await session.execute(delete(Event).where(Event.id == event.id))

        assert (await session.scalars(select(EventBonus))).all() == []
        assert (await session.scalars(select(EventTag))).all() == []

    async def test_same_bonus_cannot_be_linked_twice(
        self, session: AsyncSession, factory: Factory, rejected: Rejected
    ) -> None:
        """Бонус нельзя привязать к мероприятию дважды."""
        event = await factory.event()
        bonus = Bonus(title="ПГАС-тест")
        session.add(bonus)
        await session.flush()
        session.add(EventBonus(event_id=event.id, bonus_id=bonus.id))
        await session.flush()

        async with rejected("pk_event_bonuses"):
            session.add(EventBonus(event_id=event.id, bonus_id=bonus.id))

    async def test_used_bonus_cannot_be_deleted(
        self, session: AsyncSession, factory: Factory, rejected: Rejected
    ) -> None:
        """Бонус, привязанный к мероприятию, удалить нельзя."""
        event = await factory.event()
        bonus = Bonus(title="ПГАС-тест")
        session.add(bonus)
        await session.flush()
        session.add(EventBonus(event_id=event.id, bonus_id=bonus.id))
        await session.flush()

        async with rejected("fk_event_bonuses_bonus_id_bonuses"):
            await session.execute(delete(Bonus).where(Bonus.id == bonus.id))

    async def test_same_tag_cannot_be_linked_twice(
        self, session: AsyncSession, factory: Factory, rejected: Rejected
    ) -> None:
        """Тег нельзя привязать к мероприятию дважды."""
        event = await factory.event()
        tag = Tag(title="Выезд-тест")
        session.add(tag)
        await session.flush()
        session.add(EventTag(event_id=event.id, tag_id=tag.id))
        await session.flush()

        async with rejected("pk_event_tags"):
            session.add(EventTag(event_id=event.id, tag_id=tag.id))
