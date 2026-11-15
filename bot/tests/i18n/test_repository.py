import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.i18n.repository import LocaleRepository

pytestmark = pytest.mark.integration


@pytest.fixture
def locales(sessions: async_sessionmaker[AsyncSession]) -> LocaleRepository:
    return LocaleRepository(sessions)


class TestLocaleRepository:
    """Хранилище языков пользователей."""

    async def test_unknown_user_has_no_language(self, locales: LocaleRepository) -> None:
        """Пока язык не выбран, его нет."""
        assert await locales.get(1) is None

    async def test_language_is_saved_and_replaced(self, locales: LocaleRepository) -> None:
        """Выбранный язык сохраняется и заменяется при смене."""
        await locales.set(7_000_000_000, "en")
        first = await locales.get(7_000_000_000)

        await locales.set(7_000_000_000, "ru")
        second = await locales.get(7_000_000_000)

        assert (first, second) == ("en", "ru")

    async def test_languages_are_per_user(self, locales: LocaleRepository) -> None:
        """Язык одного пользователя не влияет на другого."""
        await locales.set(1, "en")

        assert await locales.get(2) is None

    async def test_guess_is_saved_only_once(self, locales: LocaleRepository) -> None:
        """Догаданный язык запоминается только если пользователь ещё не выбирал."""
        first = await locales.set_if_absent(1, "en")
        second = await locales.set_if_absent(1, "ru")

        assert (first, second) == ("en", "en")

    async def test_explicit_choice_beats_the_guess(self, locales: LocaleRepository) -> None:
        """Явный выбор не перезаписывается догадкой."""
        await locales.set(1, "ru")

        assert await locales.set_if_absent(1, "en") == "ru"
