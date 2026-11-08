import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Bonus, Tag
from app.database.seeders import BonusSeeder, Seeders, TagSeeder, TitleSeeder


@pytest.mark.parametrize("seeder", [BonusSeeder, TagSeeder])
class TestTitleSeeders:
    """Данные справочников с названиями."""

    def test_titles_are_not_empty(self, seeder: type[TitleSeeder]) -> None:
        """Справочник заполняется хотя бы одним значением."""
        assert seeder.titles()

    def test_titles_are_trimmed(self, seeder: type[TitleSeeder]) -> None:
        """Названия подходят под CHECK: не пустые и без пробелов по краям."""
        assert all(title and title == title.strip() for title in seeder.titles())

    def test_titles_are_unique_ignoring_case(self, seeder: type[TitleSeeder]) -> None:
        """Названия не повторяются без учёта регистра."""
        lowered = [title.lower() for title in seeder.titles()]

        assert len(lowered) == len(set(lowered))


class TestSeeders:
    """Набор сидеров."""

    def test_every_seeder_is_registered(self) -> None:
        """Все сидеры справочников входят в запуск."""
        assert set(Seeders.ORDER) == {BonusSeeder, TagSeeder}


@pytest.mark.integration
class TestSeedersInDatabase:
    """Сидеры на настоящей БД."""

    @pytest.mark.parametrize(
        ("seeder", "model"), [(BonusSeeder, Bonus), (TagSeeder, Tag)], ids=["bonus", "tag"]
    )
    async def test_fills_dictionary(
        self, session: AsyncSession, seeder: type[TitleSeeder], model: type[Bonus] | type[Tag]
    ) -> None:
        """Справочник заполняется значениями из JSON."""
        await seeder().run(session)

        stored = set(await session.scalars(select(model.title)))
        assert stored == set(seeder.titles())

    @pytest.mark.parametrize(
        ("seeder", "model"), [(BonusSeeder, Bonus), (TagSeeder, Tag)], ids=["bonus", "tag"]
    )
    async def test_second_run_changes_nothing(
        self, session: AsyncSession, seeder: type[TitleSeeder], model: type[Bonus] | type[Tag]
    ) -> None:
        """Повторный запуск не создаёт дублей."""
        await seeder().run(session)
        await seeder().run(session)

        count = await session.scalar(select(func.count()).select_from(model))
        assert count == len(seeder.titles())

    async def test_existing_title_in_other_case_is_not_duplicated(
        self, session: AsyncSession
    ) -> None:
        """Если значение уже добавлено вручную в другом регистре, дубль не создаётся."""
        session.add(Tag(title="выезд"))
        await session.flush()

        await TagSeeder().run(session)

        titles = [title.lower() for title in await session.scalars(select(Tag.title))]
        assert titles.count("выезд") == 1
