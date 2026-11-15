from datetime import UTC, datetime, timedelta

import pytest

from bot.messaging.schemas import NotificationType
from bot.queue.models import JobStatus
from bot.queue.repository import JobRepository
from tests.conftest import make_message

pytestmark = pytest.mark.integration


def ago(**delta: float) -> datetime:
    return datetime.now(UTC) - timedelta(**delta)


def ahead(**delta: float) -> datetime:
    return datetime.now(UTC) + timedelta(**delta)


class TestAdd:
    """Постановка событий в очередь."""

    async def test_event_without_time_is_ready_immediately(self, jobs: JobRepository) -> None:
        """Событие без времени отправки готово сразу."""
        await jobs.add(make_message())

        job = await jobs.claim_next()

        assert job is not None
        assert job.status is JobStatus.PROCESSING

    async def test_fields_are_stored(self, jobs: JobRepository) -> None:
        """Все поля события сохраняются в очереди."""
        message = make_message(
            type=NotificationType.SPOT_FREED,
            priority=1,
            telegram_id=7_000_000_000,
            event_id=9,
            payload={"title": "Выезд"},
            key="k",
        )

        await jobs.add(message)

        job = await jobs.claim_next()
        assert job is not None
        assert (job.message_id, job.type, job.priority) == (message.id, "spot_freed", 1)
        assert (job.telegram_id, job.event_id, job.key) == (7_000_000_000, 9, "k")
        assert job.payload == {"title": "Выезд"}
        assert job.attempts == 0

    async def test_same_event_is_added_once(self, jobs: JobRepository) -> None:
        """Повторно полученное событие игнорируется."""
        message = make_message()

        first = await jobs.add(message)
        second = await jobs.add(message)

        assert (first, second) == (True, False)
        assert len(await jobs.waiting(message.telegram_id)) == 1

    async def test_dedup_survives_finishing(self, jobs: JobRepository) -> None:
        """Даже после отправки повтор события не создаёт новое задание."""
        message = make_message()
        await jobs.add(message)
        job = await jobs.claim_next()
        assert job is not None
        await jobs.complete(job.id)

        assert await jobs.add(message) is False


class TestKeyReplacement:
    """Новое событие с тем же ключом вытесняет ещё не отправленное."""

    async def test_newer_event_replaces_waiting_one(self, jobs: JobRepository) -> None:
        """Напоминание с новым временем заменяет прежнее."""
        old = make_message(key="reminder:5", send_at=ahead(days=1))
        new = make_message(key="reminder:5", send_at=ahead(days=2))
        await jobs.add(old)

        await jobs.add(new)

        (waiting,) = await jobs.waiting(100)
        assert waiting.message_id == new.id

    async def test_other_recipient_is_untouched(self, jobs: JobRepository) -> None:
        """Ключ действует только в пределах получателя."""
        await jobs.add(make_message(key="reminder:5", telegram_id=1, send_at=ahead(days=1)))

        await jobs.add(make_message(key="reminder:5", telegram_id=2, send_at=ahead(days=1)))

        assert len(await jobs.waiting(1)) == 1
        assert len(await jobs.waiting(2)) == 1

    async def test_already_sent_one_is_kept(self, jobs: JobRepository) -> None:
        """Уже отправленное событие с тем же ключом не удаляется."""
        first = make_message(key="reminder:5")
        await jobs.add(first)
        job = await jobs.claim_next()
        assert job is not None
        await jobs.complete(job.id)

        await jobs.add(make_message(key="reminder:5", send_at=ahead(days=1)))

        assert await jobs.get(job.id) is not None


class TestReminderCleanup:
    """События, после которых напоминание не нужно."""

    async def remind(self, jobs: JobRepository, **fields: object) -> None:
        await jobs.add(
            make_message(
                type=NotificationType.REMINDER,
                event_id=5,
                key="reminder:5",
                send_at=ahead(days=1),
                **fields,
            )
        )

    @pytest.mark.parametrize(
        "notification_type",
        [
            NotificationType.EVENT_CANCELLED,
            NotificationType.REGISTRATION_CANCELLED,
            NotificationType.REGISTRATION_REJECTED,
        ],
    )
    async def test_cancellation_removes_the_reminder(
        self, jobs: JobRepository, notification_type: NotificationType
    ) -> None:
        """Отмена мероприятия или записи и отказ убирают напоминание."""
        await self.remind(jobs)

        await jobs.add(make_message(type=notification_type, event_id=5, send_at=ahead(days=3)))

        types = [job.type for job in await jobs.waiting(100)]
        assert NotificationType.REMINDER.value not in types

    async def test_moved_start_removes_the_old_reminder(self, jobs: JobRepository) -> None:
        """Перенос начала убирает старое напоминание: новое придёт отдельным событием."""
        await self.remind(jobs)

        await jobs.add(
            make_message(
                type=NotificationType.EVENT_CHANGED,
                event_id=5,
                payload={"changed": ["starts_at"]},
            )
        )

        types = [job.type for job in await jobs.waiting(100)]
        assert NotificationType.REMINDER.value not in types

    async def test_other_change_keeps_the_reminder(self, jobs: JobRepository) -> None:
        """Изменение места напоминание не трогает."""
        await self.remind(jobs)

        await jobs.add(
            make_message(
                type=NotificationType.EVENT_CHANGED,
                event_id=5,
                payload={"changed": ["location"]},
            )
        )

        types = [job.type for job in await jobs.waiting(100)]
        assert NotificationType.REMINDER.value in types

    async def test_change_without_payload_keeps_the_reminder(self, jobs: JobRepository) -> None:
        """Событие без перечня изменений напоминание не трогает."""
        await self.remind(jobs)

        await jobs.add(make_message(type=NotificationType.EVENT_CHANGED, event_id=5, payload=None))

        assert NotificationType.REMINDER.value in [j.type for j in await jobs.waiting(100)]

    async def test_other_event_and_other_user_are_untouched(self, jobs: JobRepository) -> None:
        """Напоминания других мероприятий и других людей остаются."""
        await self.remind(jobs)
        await jobs.add(
            make_message(
                type=NotificationType.REMINDER,
                event_id=6,
                key="reminder:6",
                send_at=ahead(days=1),
            )
        )
        await jobs.add(
            make_message(
                type=NotificationType.REMINDER,
                event_id=5,
                key="reminder:5",
                telegram_id=200,
                send_at=ahead(days=1),
            )
        )

        await jobs.add(make_message(type=NotificationType.EVENT_CANCELLED, event_id=5))

        assert len([j for j in await jobs.waiting(100) if j.type == "reminder"]) == 1
        assert len(await jobs.waiting(200)) == 1

    async def test_event_without_event_id_removes_nothing(self, jobs: JobRepository) -> None:
        """Событие без мероприятия не может ничего отменить."""
        await self.remind(jobs)

        await jobs.add(make_message(type=NotificationType.EVENT_CANCELLED, event_id=None))

        assert NotificationType.REMINDER.value in [j.type for j in await jobs.waiting(100)]


class TestClaim:
    """Выбор следующего задания."""

    async def test_high_priority_goes_first_then_earlier_time(self, jobs: JobRepository) -> None:
        """Сначала высокий приоритет, внутри приоритета — раньше назначенное время."""
        low = make_message(priority=3, send_at=ago(hours=5))
        late = make_message(priority=2, send_at=ago(hours=1))
        early = make_message(priority=2, send_at=ago(hours=3))
        urgent = make_message(priority=1, send_at=ago(hours=1))
        for message in (low, late, early, urgent):
            await jobs.add(message)

        order = []
        while (job := await jobs.claim_next()) is not None:
            order.append(job.message_id)

        assert order == [urgent.id, early.id, late.id, low.id]

    async def test_future_jobs_wait(self, jobs: JobRepository) -> None:
        """Задание с будущим временем не берётся, пока не наступит его час."""
        await jobs.add(make_message(send_at=ahead(hours=1)))

        assert await jobs.claim_next() is None

    async def test_empty_queue(self, jobs: JobRepository) -> None:
        """Пустая очередь возвращает None."""
        assert await jobs.claim_next() is None

    async def test_job_is_claimed_once(self, jobs: JobRepository) -> None:
        """Взятое задание второй раз не выдаётся."""
        await jobs.add(make_message())

        first = await jobs.claim_next()
        second = await jobs.claim_next()

        assert first is not None
        assert second is None

    async def test_concurrent_claims_do_not_share_a_job(self, jobs: JobRepository) -> None:
        """Два воркера одновременно не получают одно и то же задание."""
        import asyncio

        for _ in range(4):
            await jobs.add(make_message())

        claimed = await asyncio.gather(*(jobs.claim_next() for _ in range(4)))

        ids = [job.id for job in claimed if job is not None]
        assert len(ids) == len(set(ids)) == 4


class TestFinishing:
    """Итоги выполнения."""

    async def test_complete(self, jobs: JobRepository) -> None:
        """Отправленное задание получает статус done и время завершения."""
        await jobs.add(make_message())
        job = await jobs.claim_next()
        assert job is not None

        await jobs.complete(job.id)

        stored = await jobs.get(job.id)
        assert stored is not None
        assert stored.status is JobStatus.DONE
        assert stored.finished_at is not None
        assert stored.attempts == 1

    async def test_fail(self, jobs: JobRepository) -> None:
        """Проваленное задание хранит причину."""
        await jobs.add(make_message())
        job = await jobs.claim_next()
        assert job is not None

        await jobs.fail(job.id, "Бот заблокирован")

        stored = await jobs.get(job.id)
        assert stored is not None
        assert stored.status is JobStatus.FAILED
        assert stored.last_error == "Бот заблокирован"

    async def test_retry_moves_the_job_forward(self, jobs: JobRepository) -> None:
        """Повтор возвращает задание в очередь на более позднее время и считает попытку."""
        await jobs.add(make_message())
        job = await jobs.claim_next()
        assert job is not None

        await jobs.retry(job.id, ahead(hours=1), "Таймаут")

        stored = await jobs.get(job.id)
        assert stored is not None
        assert stored.status is JobStatus.WAITING
        assert stored.attempts == 1
        assert stored.last_error == "Таймаут"
        assert await jobs.claim_next() is None

    async def test_unknown_job(self, jobs: JobRepository) -> None:
        """Несуществующее задание — None."""
        assert await jobs.get(999999) is None


class TestMaintenance:
    """Обслуживание очереди."""

    async def test_stuck_jobs_return_to_the_queue(self, jobs: JobRepository) -> None:
        """После сбоя невыполненные задания возвращаются в очередь."""
        await jobs.add(make_message())
        await jobs.claim_next()

        restored = await jobs.requeue_stuck()

        assert restored == 1
        assert await jobs.claim_next() is not None

    async def test_nothing_stuck(self, jobs: JobRepository) -> None:
        """Если зависших заданий нет, ничего не меняется."""
        await jobs.add(make_message())

        assert await jobs.requeue_stuck() == 0

    async def test_old_finished_jobs_are_purged(self, jobs: JobRepository) -> None:
        """Старые завершённые задания удаляются, свежие и ждущие остаются."""
        await jobs.add(make_message())
        job = await jobs.claim_next()
        assert job is not None
        await jobs.complete(job.id)
        await jobs.add(make_message(telegram_id=2))

        fresh = await jobs.purge_finished(timedelta(days=7))
        old = await jobs.purge_finished(timedelta(seconds=-1))

        assert (fresh, old) == (0, 1)
        assert len(await jobs.waiting(2)) == 1
