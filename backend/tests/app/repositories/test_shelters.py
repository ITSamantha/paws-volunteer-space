import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.database.models.enums import ContactType
from app.repositories.shelters import ShelterRepository
from tests.app.database.factory import Factory

pytestmark = pytest.mark.integration


class TestShelterRepository:
    """Доступ к приютам на настоящей БД."""

    async def test_duplicate_contact_becomes_conflict(
        self, session: AsyncSession, factory: Factory
    ) -> None:
        """Повторяющийся контакт превращается в понятную ошибку."""
        shelter = await factory.shelter()
        repository = ShelterRepository(session)
        await repository.add_contact(shelter.id, ContactType.PHONE, "+78125550000")

        with pytest.raises(ConflictError, match="Такой контакт"):
            await repository.add_contact(shelter.id, ContactType.PHONE, "+78125550000")

    async def test_other_violations_are_not_hidden(
        self, session: AsyncSession, factory: Factory
    ) -> None:
        """Другие нарушения БД (например, пустое значение) не маскируются под дубль."""
        shelter = await factory.shelter()

        with pytest.raises(IntegrityError, match="value_not_empty"):
            await ShelterRepository(session).add_contact(shelter.id, ContactType.PHONE, "  ")
