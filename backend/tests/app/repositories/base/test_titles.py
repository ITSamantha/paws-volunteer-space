import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.database.models import Bonus
from app.repositories.base.titles import TitleRepository
from tests.app.database.factory import Factory

pytestmark = pytest.mark.integration


class TestTitleRepository:
    """Доступ к справочнику на настоящей БД."""

    def repository(self, session: AsyncSession) -> TitleRepository[Bonus]:
        return TitleRepository(session, Bonus, "uq_bonuses_title_lower", "Такой бонус уже есть")

    async def test_duplicate_title_becomes_conflict(
        self, session: AsyncSession, factory: Factory
    ) -> None:
        """Нарушение уникальности названия превращается в понятную ошибку."""
        user = await factory.user()
        repository = self.repository(session)
        await repository.add("ПГАС", user.id)

        with pytest.raises(ConflictError, match="Такой бонус уже есть"):
            await repository.add("пгас", user.id)

    async def test_other_violations_are_not_hidden(
        self, session: AsyncSession, factory: Factory
    ) -> None:
        """Другие нарушения БД (например, пробелы по краям) не маскируются под дубль."""
        user = await factory.user()

        with pytest.raises(IntegrityError, match="title_trimmed"):
            await self.repository(session).add(" ПГАС", user.id)
