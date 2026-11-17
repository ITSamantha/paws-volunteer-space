from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Broadcast
from app.schemas.pagination import Pagination


class BroadcastRepository:
    """Доступ к рассылкам."""

    def __init__(self, session: AsyncSession) -> None:
        """Работает в переданной сессии."""
        self.__session = session

    async def get(self, broadcast_id: int) -> Broadcast | None:
        """Находит рассылку по ID."""
        broadcast = await self.__session.get(Broadcast, broadcast_id)

        return broadcast

    async def add(self, broadcast: Broadcast) -> None:
        """Добавляет рассылку."""
        self.__session.add(broadcast)

        await self.__session.flush()

    async def search(self, pagination: Pagination) -> tuple[list[Broadcast], int]:
        """Страница рассылок, сначала новые."""
        total = await self.__session.scalar(select(func.count()).select_from(Broadcast))
        statement = (
            select(Broadcast)
            .order_by(Broadcast.created_at.desc(), Broadcast.id.desc())
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        broadcasts = await self.__session.scalars(statement)

        return list(broadcasts), total or 0
