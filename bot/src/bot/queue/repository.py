from datetime import UTC, datetime, timedelta
from typing import ClassVar

from sqlalchemy import ColumnElement, and_, delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.messaging.schemas import NotificationMessage, NotificationType
from bot.queue.models import Job, JobStatus


class JobRepository:
    """Хранилище очереди доставки."""

    REMINDER_KILLERS: ClassVar[frozenset[NotificationType]] = frozenset(
        {
            NotificationType.EVENT_CANCELLED,
            NotificationType.REGISTRATION_CANCELLED,
            NotificationType.REGISTRATION_REJECTED,
        }
    )

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        """Работает через переданную фабрику сессий; каждая операция — своя транзакция."""
        self.__sessions = sessions

    async def add(self, message: NotificationMessage) -> bool:
        """Кладёт событие в очередь; False, если такое уже получали.

        Новое событие с тем же ключом вытесняет ещё не отправленное. Отмена мероприятия или записи,
        отказ и перенос начала убирают ждущие напоминания об этом мероприятии.
        """
        now = datetime.now(UTC)

        async with self.__sessions() as session, session.begin():
            if await session.scalar(select(Job.id).where(Job.message_id == message.id)):
                return False

            if message.key is not None:
                await self.__drop_waiting(session, Job.key == message.key, message.telegram_id)

            if self.__stops_reminders(message) and message.event_id is not None:
                await self.__drop_waiting(
                    session,
                    (Job.event_id == message.event_id)
                    & (Job.type == NotificationType.REMINDER.value),
                    message.telegram_id,
                )

            await session.execute(
                insert(Job)
                .values(
                    message_id=message.id,
                    telegram_id=message.telegram_id,
                    type=message.type.value,
                    priority=message.priority,
                    event_id=message.event_id,
                    payload=message.payload,
                    key=message.key,
                    status=JobStatus.WAITING,
                    run_at=message.send_at or now,
                    attempts=0,
                    created_at=now,
                )
                .on_conflict_do_nothing(index_elements=["message_id"])
            )

        return True

    async def claim_next(self) -> Job | None:
        """Берёт самое важное готовое к отправке задание и помечает его выполняемым."""
        now = datetime.now(UTC)

        async with self.__sessions() as session, session.begin():
            job = await session.scalar(
                select(Job)
                .where(Job.status == JobStatus.WAITING, Job.run_at <= now)
                .order_by(Job.priority, Job.run_at, Job.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )

            if job is None:
                return None

            job.status = JobStatus.PROCESSING
            await session.flush()
            session.expunge(job)

            return job

    async def complete(self, job_id: int) -> None:
        """Отмечает задание отправленным."""
        await self.__finish(job_id, JobStatus.DONE, None)

    async def fail(self, job_id: int, error: str) -> None:
        """Отмечает задание проваленным без повторов."""
        await self.__finish(job_id, JobStatus.FAILED, error)

    async def retry(self, job_id: int, run_at: datetime, error: str) -> None:
        """Возвращает задание в очередь: следующая попытка не раньше run_at."""
        async with self.__sessions() as session, session.begin():
            await session.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(
                    status=JobStatus.WAITING,
                    run_at=run_at,
                    attempts=Job.attempts + 1,
                    last_error=error,
                )
            )

    async def requeue_stuck(self) -> int:
        """После сбоя возвращает в очередь задания, которые не успели завершиться."""
        async with self.__sessions() as session, session.begin():
            result = await session.execute(
                update(Job)
                .where(Job.status == JobStatus.PROCESSING)
                .values(status=JobStatus.WAITING)
                .returning(Job.id)
            )

            return len(result.all())

    async def purge_finished(self, older_than: timedelta) -> int:
        """Удаляет давно завершённые задания; свежие остаются для защиты от повторов."""
        border = datetime.now(UTC) - older_than

        async with self.__sessions() as session, session.begin():
            result = await session.execute(
                delete(Job)
                .where(Job.status.in_([JobStatus.DONE, JobStatus.FAILED]), Job.finished_at < border)
                .returning(Job.id)
            )

            return len(result.all())

    async def get(self, job_id: int) -> Job | None:
        """Задание по ID."""
        async with self.__sessions() as session:
            job = await session.get(Job, job_id)

            if job is not None:
                session.expunge(job)

            return job

    async def waiting(self, telegram_id: int) -> list[Job]:
        """Ждущие отправки задания получателя в порядке очереди."""
        async with self.__sessions() as session:
            rows = await session.scalars(
                select(Job)
                .where(Job.telegram_id == telegram_id, Job.status == JobStatus.WAITING)
                .order_by(Job.priority, Job.run_at, Job.id)
            )
            jobs = list(rows)

            for job in jobs:
                session.expunge(job)

            return jobs

    async def __finish(self, job_id: int, status: JobStatus, error: str | None) -> None:
        """Завершает задание с итоговым статусом."""
        async with self.__sessions() as session, session.begin():
            await session.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(
                    status=status,
                    attempts=Job.attempts + 1,
                    last_error=error,
                    finished_at=datetime.now(UTC),
                )
            )

    @staticmethod
    async def __drop_waiting(
        session: AsyncSession, condition: ColumnElement[bool], telegram_id: int
    ) -> None:
        """Удаляет ещё не отправленные задания получателя, подходящие под условие."""
        await session.execute(
            delete(Job).where(
                and_(Job.telegram_id == telegram_id, Job.status == JobStatus.WAITING, condition)
            )
        )

    @classmethod
    def __stops_reminders(cls, message: NotificationMessage) -> bool:
        """Делает ли событие ждущие напоминания бессмысленными."""
        if message.type in cls.REMINDER_KILLERS:
            return True

        changed = (message.payload or {}).get("changed", [])

        return message.type is NotificationType.EVENT_CHANGED and "starts_at" in changed
