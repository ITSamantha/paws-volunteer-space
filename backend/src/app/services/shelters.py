from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.database.models import Shelter, ShelterContact, User
from app.repositories.shelters import ShelterRepository
from app.schemas.shelters import ContactCreate, ShelterCreate, ShelterUpdate
from app.services.access import Access


class ShelterService:
    """Сценарии работы с приютами: смотреть может любой, менять — персонал, удалять — админ."""

    def __init__(self, session: AsyncSession) -> None:
        """Работает в переданной сессии."""
        self.__session = session
        self.__shelters = ShelterRepository(session)

    async def list_all(self) -> list[Shelter]:
        """Все приюты."""
        shelters = await self.__shelters.list_all()

        return shelters

    async def get(self, shelter_id: int) -> Shelter:
        """Приют по ID."""
        shelter = await self.__require(shelter_id)

        return shelter

    async def create(self, data: ShelterCreate, current_user: User) -> Shelter:
        """Добавляет приют; организаторы и администраторы."""
        Access.require_staff(current_user)

        fields = data.model_dump(exclude={"contacts"})
        contacts = [ShelterContact(type=item.type, value=item.value) for item in data.contacts]
        shelter = Shelter(**fields, contacts=contacts)

        await self.__shelters.add(shelter)
        await self.__session.commit()

        return shelter

    async def update(self, shelter_id: int, data: ShelterUpdate, current_user: User) -> Shelter:
        """Изменяет приют; организаторы и администраторы."""
        Access.require_staff(current_user)
        shelter = await self.__require(shelter_id)

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(shelter, field, value)

        await self.__shelters.flush()
        await self.__session.commit()

        return shelter

    async def delete(self, shelter_id: int, current_user: User) -> None:
        """Мягко удаляет приют; только администраторы."""
        Access.require_admin(current_user)
        shelter = await self.__require(shelter_id)

        await self.__shelters.delete(shelter)
        await self.__session.commit()

    async def add_contact(
        self, shelter_id: int, data: ContactCreate, current_user: User
    ) -> ShelterContact:
        """Добавляет контакт приюту; организаторы и администраторы."""
        Access.require_staff(current_user)
        shelter = await self.__require(shelter_id)

        contact = await self.__shelters.add_contact(shelter.id, data.type, data.value)
        await self.__session.commit()

        return contact

    async def delete_contact(self, shelter_id: int, contact_id: int, current_user: User) -> None:
        """Удаляет контакт приюта; организаторы и администраторы."""
        Access.require_staff(current_user)
        shelter = await self.__require(shelter_id)

        contact = await self.__shelters.get_contact(shelter.id, contact_id)

        if contact is None:
            raise NotFoundError("Контакт не найден")

        await self.__shelters.delete_contact(contact)
        await self.__session.commit()

    async def __require(self, shelter_id: int) -> Shelter:
        """Возвращает приют или выбрасывает NotFoundError."""
        shelter = await self.__shelters.get(shelter_id)

        if shelter is None:
            raise NotFoundError("Приют не найден")

        return shelter
