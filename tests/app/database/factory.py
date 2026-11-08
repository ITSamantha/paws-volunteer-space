from datetime import UTC, datetime, timedelta
from itertools import count
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Event, Registration, Shelter, User, UserRole
from app.database.models.enums import RoleType


class Factory:
    """Создание записей для проверок на настоящей БД."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._telegram_ids = count(1000)

    async def user(self, **fields: Any) -> User:
        values: dict[str, Any] = {"telegram_id": next(self._telegram_ids), "phone": "+79990000000"}

        user = User(**{**values, **fields})

        self._session.add(user)
        await self._session.flush()

        return user

    async def role(self, user: User, role: RoleType, granted_by: User | None = None) -> UserRole:
        granted = UserRole(user_id=user.id, role=role, granted_by=(granted_by or user).id)

        self._session.add(granted)
        await self._session.flush()

        return granted

    async def shelter(self, **fields: Any) -> Shelter:
        values: dict[str, Any] = {"title": "Приют", "address": "Санкт-Петербург"}

        shelter = Shelter(**{**values, **fields})

        self._session.add(shelter)
        await self._session.flush()

        return shelter

    async def event(self, **fields: Any) -> Event:
        organizer = fields.pop("organizer", None) or await self.user()

        values: dict[str, Any] = {
            "title": "Выезд",
            "starts_at": datetime.now(UTC) + timedelta(days=1),
            "location": "Остановка",
            "capacity": 5,
            "created_by": organizer.id,
        }

        event = Event(**{**values, **fields})

        self._session.add(event)
        await self._session.flush()

        return event

    async def registration(self, event: Event, user: User, **fields: Any) -> Registration:
        registration = Registration(event_id=event.id, user_id=user.id, **fields)

        self._session.add(registration)
        await self._session.flush()

        return registration
