from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, UnprocessableError
from app.database.models import Broadcast, Registration, User
from app.database.models.enums import BroadcastAudience, BroadcastStatus, NotificationType
from app.repositories.broadcasts import BroadcastRepository
from app.repositories.event.base import EventRepository
from app.repositories.users import UserRepository
from app.schemas.broadcasts import BroadcastCreate, BroadcastUpdate
from app.schemas.pagination import Pagination
from app.services.access import Access
from app.services.notifications import NotificationService


class BroadcastService:
    """Черновики рассылок и их отправка в Kafka после сохранения."""

    def __init__(self, session: AsyncSession) -> None:
        """Работает в переданной сессии."""
        self.__session = session
        self.__broadcasts = BroadcastRepository(session)
        self.__events = EventRepository(session)
        self.__users = UserRepository(session)
        self.__notifications = NotificationService(session)

    async def search(
        self, pagination: Pagination, current_user: User
    ) -> tuple[list[Broadcast], int]:
        """Список рассылок; администраторам, организаторам и SMM."""
        Access.require_publisher(current_user)
        page = await self.__broadcasts.search(pagination)

        return page

    async def get(self, broadcast_id: int, current_user: User) -> Broadcast:
        """Карточка рассылки."""
        Access.require_publisher(current_user)
        broadcast = await self.__require(broadcast_id)

        return broadcast

    async def create(self, data: BroadcastCreate, current_user: User) -> Broadcast:
        """Сохраняет черновик."""
        Access.require_publisher(current_user)
        await self.__require_event(data.audience, data.event_id)
        broadcast = Broadcast(
            author_id=current_user.id,
            text=data.text,
            audience=data.audience,
            event_id=data.event_id,
        )

        await self.__broadcasts.add(broadcast)
        await self.__session.commit()

        return broadcast

    async def update(
        self, broadcast_id: int, data: BroadcastUpdate, current_user: User
    ) -> Broadcast:
        """Правит черновик. Чужой черновик может править только администратор."""
        Access.require_publisher(current_user)
        broadcast = await self.__require(broadcast_id)
        self.__require_editable(broadcast, current_user)

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(broadcast, field, value)

        if broadcast.audience is not BroadcastAudience.EVENT_PARTICIPANTS:
            broadcast.event_id = None

        await self.__require_event(broadcast.audience, broadcast.event_id)
        await self.__session.commit()

        return broadcast

    async def send(self, broadcast_id: int, current_user: User) -> Broadcast:
        """Отправляет черновик выбранной аудитории. Повторно отправить нельзя."""
        Access.require_publisher(current_user)
        broadcast = await self.__require(broadcast_id)
        self.__require_editable(broadcast, current_user)
        recipients = await self.__recipients(broadcast)

        broadcast.status = BroadcastStatus.SENT
        broadcast.sent_at = datetime.now(UTC)
        self.__notifications.add(
            recipients,
            NotificationType.BROADCAST,
            broadcast.event_id,
            {"text": broadcast.text},
        )
        await self.__notifications.commit()

        return broadcast

    async def __recipients(self, broadcast: Broadcast) -> list[int]:
        """Кому уходит эта рассылка."""
        if broadcast.audience is BroadcastAudience.ALL:
            recipients = await self.__users.active_ids()
        elif broadcast.audience is BroadcastAudience.ANNOUNCEMENTS_SUBSCRIBERS:
            recipients = await self.__users.subscriber_ids()
        else:
            recipients = await self.__events.participant_ids(
                broadcast.event_id or 0, Registration.NOTIFIABLE_STATUSES
            )

        return recipients

    async def __require(self, broadcast_id: int) -> Broadcast:
        """Возвращает рассылку или выбрасывает NotFoundError."""
        broadcast = await self.__broadcasts.get(broadcast_id)

        if broadcast is None:
            raise NotFoundError("Рассылка не найдена")

        return broadcast

    async def __require_event(self, audience: BroadcastAudience, event_id: int | None) -> None:
        """Проверяет, что мероприятие указано и существует ровно когда это нужно аудитории."""
        needs_event = audience is BroadcastAudience.EVENT_PARTICIPANTS

        if needs_event != (event_id is not None):
            raise UnprocessableError(
                "Мероприятие нужно только для аудитории «участники мероприятия»"
            )

        if event_id is None:
            return

        event = await self.__events.get(event_id)

        if event is None:
            raise UnprocessableError("Мероприятие не найдено")

    @staticmethod
    def __require_editable(broadcast: Broadcast, current_user: User) -> None:
        """Черновик правит автор или администратор."""
        if broadcast.status is not BroadcastStatus.DRAFT:
            raise ConflictError("Можно править только черновик")

        if broadcast.author_id != current_user.id and not Access.is_admin(current_user):
            raise ForbiddenError("Чужой черновик может править только администратор")
