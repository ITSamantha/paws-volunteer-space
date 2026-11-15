import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.enums import NotificationType
from app.messaging.publisher import Publishing
from app.messaging.schemas import NotificationMessage
from app.repositories.users import UserRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Staged:
    """Событие, ожидающее коммита."""

    user_ids: tuple[int, ...]
    type: NotificationType
    event_id: int | None
    payload: dict[str, Any]
    send_at: datetime | None
    key: str | None


class NotificationService:
    """Отправка событий боту из эндпоинтов.

    Эндпоинт описывает события через add(), а вместо session.commit() вызывает commit():
    изменения сохраняются, и только после этого события уходят в Kafka. Если коммит не
    удался, транзакция откатывается, а накопленные события отбрасываются: бот не узнает о том,
    чего не произошло. Сбой брокера или поиска получателей запрос не ломает: действие уже
    сохранено, ошибка пишется в лог, остальные события продолжают отправляться.
    Очередь, время отправки и повторы целиком на стороне бота.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Работает в переданной сессии: коммитит её и ищет в ней Telegram ID получателей."""
        self.__session = session
        self.__users = UserRepository(session)
        self.__staged: list[Staged] = []

    def add(
        self,
        user_ids: Iterable[int],
        notification_type: NotificationType,
        event_id: int | None,
        payload: dict[str, Any],
        send_at: datetime | None = None,
        key: str | None = None,
    ) -> None:
        """Запоминает событие для каждого получателя; send_at=None значит «сразу»."""
        recipients = tuple(dict.fromkeys(user_ids))

        if recipients:
            self.__staged.append(
                Staged(recipients, notification_type, event_id, payload, send_at, key)
            )

    def discard(self) -> None:
        """Отбрасывает накопленные события."""
        self.__staged = []

    async def commit(self) -> None:
        """Сохраняет изменения и после успешного коммита отправляет накопленные события."""
        try:
            await self.__session.commit()
        except Exception:
            await self.__session.rollback()
            self.discard()
            raise

        await self.send()

    async def send(self) -> None:
        """Публикует накопленные события; ошибки не выбрасывает."""
        staged, self.__staged = self.__staged, []

        if not staged:
            return

        try:
            telegram_ids = await self.__users.telegram_ids(
                {user_id for item in staged for user_id in item.user_ids}
            )
        except Exception:
            logger.exception("Не удалось найти получателей, события боту не отправлены")
            return

        for item in staged:
            for user_id in item.user_ids:
                await self.__publish(item, user_id, telegram_ids.get(user_id))

    async def __publish(self, item: Staged, user_id: int, telegram_id: int | None) -> None:
        """Публикует одно событие; сбой не мешает остальным."""
        if telegram_id is None:
            logger.warning("Получатель %s не найден, событие %s пропущено", user_id, item.type)
            return

        try:
            await Publishing.get().publish(
                NotificationMessage(
                    type=item.type,
                    priority=item.type.priority,
                    telegram_id=telegram_id,
                    event_id=item.event_id,
                    payload=item.payload,
                    send_at=item.send_at,
                    key=item.key,
                    created_at=datetime.now(UTC),
                )
            )
        except Exception:
            logger.exception("Событие %s не отправлено боту", item.type.value)
