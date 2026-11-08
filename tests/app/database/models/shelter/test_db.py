import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Shelter, ShelterContact
from app.database.models.enums import ContactType
from tests.app.database.conftest import Rejected
from tests.app.database.factory import Factory

pytestmark = pytest.mark.integration


class TestShelterInDatabase:
    """Таблицы shelters и shelter_contacts на настоящей БД."""

    async def test_approval_is_not_required_by_default(self, factory: Factory) -> None:
        """Записи в новый приют подтверждаются автоматически."""
        shelter = await factory.shelter()

        assert shelter.is_approval_required is False

    async def test_contacts_are_deleted_with_shelter(
        self, session: AsyncSession, factory: Factory
    ) -> None:
        """Контакты удаляются вместе с приютом."""
        shelter = await factory.shelter()
        session.add(ShelterContact(shelter_id=shelter.id, type=ContactType.PHONE, value="+7999"))
        await session.flush()

        await session.execute(delete(Shelter).where(Shelter.id == shelter.id))

        contacts = (await session.scalars(select(ShelterContact))).all()
        assert contacts == []

    async def test_empty_contact_is_rejected(
        self, session: AsyncSession, factory: Factory, rejected: Rejected
    ) -> None:
        """Пустое значение контакта отклоняется."""
        shelter = await factory.shelter()

        async with rejected("ck_shelter_contacts_value_not_empty"):
            session.add(ShelterContact(shelter_id=shelter.id, type=ContactType.EMAIL, value="  "))

    async def test_duplicate_contact_is_rejected(
        self, session: AsyncSession, factory: Factory, rejected: Rejected
    ) -> None:
        """Тот же контакт нельзя добавить дважды, а тот же тип с другим значением можно."""
        shelter = await factory.shelter()
        session.add(ShelterContact(shelter_id=shelter.id, type=ContactType.PHONE, value="+1"))
        session.add(ShelterContact(shelter_id=shelter.id, type=ContactType.PHONE, value="+2"))
        await session.flush()

        async with rejected("uq_shelter_contacts_shelter_id_type_value"):
            session.add(ShelterContact(shelter_id=shelter.id, type=ContactType.PHONE, value="+1"))
