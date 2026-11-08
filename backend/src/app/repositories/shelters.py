from datetime import UTC, datetime

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError
from app.database.models import Shelter, ShelterContact
from app.database.models.enums import ContactType


class ShelterRepository:
    """Доступ к приютам и их контактам. Мягко удалённые приюты не возвращаются."""

    DUPLICATE_CONTACT: str = "uq_shelter_contacts_shelter_id_type_value"

    def __init__(self, session: AsyncSession) -> None:
        """Работает в переданной сессии."""
        self.__session = session

    async def list_all(self) -> list[Shelter]:
        """Все приюты по алфавиту с контактами."""
        statement = self.__select().order_by(func.lower(Shelter.title), Shelter.id)
        shelters = await self.__session.scalars(statement)

        return list(shelters)

    async def get(self, shelter_id: int) -> Shelter | None:
        """Находит приют по ID вместе с контактами."""
        shelter = await self.__session.scalar(self.__select().where(Shelter.id == shelter_id))

        return shelter

    async def add(self, shelter: Shelter) -> None:
        """Добавляет приют вместе с контактами."""
        self.__session.add(shelter)

        await self.flush()

    async def flush(self) -> None:
        """Записывает изменения; повторяющийся контакт превращается в ConflictError."""
        try:
            async with self.__session.begin_nested():
                await self.__session.flush()
        except IntegrityError as error:
            if self.DUPLICATE_CONTACT in str(error.orig):
                raise ConflictError("Такой контакт у приюта уже есть") from None

            raise

    async def delete(self, shelter: Shelter) -> None:
        """Мягко удаляет приют."""
        shelter.deleted_at = datetime.now(UTC)

        await self.flush()

    async def add_contact(
        self, shelter_id: int, contact_type: ContactType, value: str
    ) -> ShelterContact:
        """Добавляет контакт приюту."""
        contact = ShelterContact(shelter_id=shelter_id, type=contact_type, value=value)
        self.__session.add(contact)

        await self.flush()

        return contact

    async def get_contact(self, shelter_id: int, contact_id: int) -> ShelterContact | None:
        """Находит контакт, принадлежащий приюту."""
        statement = select(ShelterContact).where(
            ShelterContact.id == contact_id, ShelterContact.shelter_id == shelter_id
        )
        contact = await self.__session.scalar(statement)

        return contact

    async def delete_contact(self, contact: ShelterContact) -> None:
        """Удаляет контакт."""
        await self.__session.delete(contact)
        await self.__session.flush()

    def __select(self) -> Select[Shelter]:
        """Базовый запрос: не удалённые приюты с загруженными контактами."""
        return (
            select(Shelter)
            .where(Shelter.deleted_at.is_(None))
            .options(selectinload(Shelter.contacts))
            .execution_options(populate_existing=True)
        )
