from app.database.models import User
from app.database.models.enums import RoleType
from tests.app.database.factory import Factory


def as_user(user: User) -> dict[str, str]:
    return {"X-Telegram-Id": str(user.telegram_id)}


async def make_admin(factory: Factory) -> User:
    admin = await factory.user()

    await factory.role(admin, RoleType.ADMIN)

    return admin


async def make_organizer(factory: Factory, admin: User) -> User:
    organizer = await factory.user()

    await factory.role(organizer, RoleType.ORGANIZER, admin)

    return organizer
