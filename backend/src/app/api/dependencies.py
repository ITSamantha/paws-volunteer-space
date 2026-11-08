import secrets
from typing import Annotated

from fastapi import Depends, Header, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.database.models import User
from app.database.models.enums import UserStatus
from app.database.session import Database
from app.repositories.users import UserRepository
from app.schemas.pagination import Pagination

DatabaseSession = Annotated[AsyncSession, Depends(Database.session)]
BEARER = HTTPBearer(auto_error=False, description="Токен сервиса (бота)")


class Dependencies:
    """Общие зависимости эндпоинтов.

    Бот подтверждает себя токеном сервиса (Authorization: Bearer) и передаёт в заголовке
    X-Telegram-Id Telegram ID того, кого обслуживает.
    """

    @staticmethod
    async def service(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(BEARER)],
    ) -> None:
        """Проверяет токен сервиса (бота) из заголовка Authorization."""
        expected = Settings.get().auth.bot_token.get_secret_value()

        if credentials is None or not secrets.compare_digest(credentials.credentials, expected):
            raise UnauthorizedError("Неверный или отсутствующий токен")

    @staticmethod
    async def telegram_id(
        x_telegram_id: Annotated[int | None, Header(gt=0)] = None,
    ) -> int:
        """Возвращает Telegram ID из заголовка X-Telegram-Id."""
        if x_telegram_id is None:
            raise UnauthorizedError("Не указан заголовок X-Telegram-Id")

        return x_telegram_id

    @staticmethod
    async def current_user(
        telegram_id: Annotated[int, Depends(telegram_id)],
        session: DatabaseSession,
    ) -> User:
        """Находит пользователя, от имени которого действует бот; заблокированным доступ закрыт."""
        user = await UserRepository(session).get_by_telegram_id(telegram_id)

        if user is None:
            raise UnauthorizedError("Пользователь не зарегистрирован")

        if user.status is UserStatus.BLOCKED:
            raise ForbiddenError("Пользователь заблокирован")

        return user

    @staticmethod
    async def pagination(
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> Pagination:
        """Параметры постраничной выборки limit и offset."""
        return Pagination(limit=limit, offset=offset)


CurrentTelegramId = Annotated[int, Depends(Dependencies.telegram_id)]
CurrentUser = Annotated[User, Depends(Dependencies.current_user)]
PageParams = Annotated[Pagination, Depends(Dependencies.pagination)]
