from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Event, Notification, User
from app.database.models.enums import RoleType
from tests.app.database.factory import Factory


def as_user(user: User) -> dict[str, str]:
    return {"X-Telegram-Id": str(user.telegram_id)}


async def make_admin(factory: Factory) -> User:
    admin = await factory.admin()

    return admin


async def make_organizer(factory: Factory, admin: User) -> User:
    organizer = await factory.user()

    await factory.role(organizer, RoleType.ORGANIZER, admin)

    return organizer


async def notifications_of(session: AsyncSession, event: Event) -> list[Notification]:
    rows = await session.scalars(
        select(Notification).where(Notification.event_id == event.id).order_by(Notification.id)
    )

    return list(rows)
