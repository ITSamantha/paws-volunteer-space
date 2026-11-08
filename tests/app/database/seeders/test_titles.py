import pytest

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
