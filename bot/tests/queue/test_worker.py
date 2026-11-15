import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config import QueueSettings
from bot.i18n.repository import LocaleRepository
from bot.i18n.translator import Translator
from bot.messaging.schemas import NotificationType
from bot.queue.models import JobStatus
from bot.queue.repository import JobRepository
from bot.queue.worker import QueueWorker
from bot.sending.errors import DeliveryError
from bot.sending.messages import Messages
from tests.conftest import make_message
from tests.support import wait_until

pytestmark = pytest.mark.integration


class FakeSender:
    """Запоминает отправленное; ошибки берёт из очереди заготовленных."""

    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []
        self.errors: list[Exception] = []

    async def send(self, telegram_id: int, text: str) -> None:
        if self.errors:
            raise self.errors.pop(0)

        self.sent.append((telegram_id, text))


@pytest.fixture
def sender() -> FakeSender:
    return FakeSender()


@pytest.fixture
def settings() -> QueueSettings:
    return QueueSettings(
        _env_file=None, send_interval=0, calm_period=0.01, max_attempts=3, retry_delay=60
    )


@pytest.fixture
def locales(sessions: async_sessionmaker[AsyncSession]) -> LocaleRepository:
    return LocaleRepository(sessions)


@pytest.fixture
def worker(
    jobs: JobRepository, locales: LocaleRepository, sender: FakeSender, settings: QueueSettings
) -> QueueWorker:
    return QueueWorker(jobs, locales, sender, Messages(Translator("Europe/Moscow")), settings)


class TestRunOnce:
    """Обработка одного задания."""

    async def test_empty_queue(self, worker: QueueWorker) -> None:
        """Пустая очередь: делать нечего."""
        assert await worker.run_once() is False

    async def test_message_is_rendered_and_sent(
        self, jobs: JobRepository, worker: QueueWorker, sender: FakeSender
    ) -> None:
        """Сообщение формируется из типа и данных и уходит получателю; задание закрывается."""
        await jobs.add(make_message(telegram_id=555, payload={"title": "Выезд"}))

        assert await worker.run_once() is True

        assert sender.sent[0][0] == 555
        assert "Выезд" in sender.sent[0][1]
        assert await worker.run_once() is False

    async def test_job_is_done_after_sending(
        self, jobs: JobRepository, worker: QueueWorker
    ) -> None:
        """После отправки задание получает статус done."""
        message = make_message()
        await jobs.add(message)

        await worker.run_once()

        assert await jobs.waiting(message.telegram_id) == []

    async def test_message_uses_the_recipients_language(
        self,
        jobs: JobRepository,
        locales: LocaleRepository,
        worker: QueueWorker,
        sender: FakeSender,
    ) -> None:
        """Текст формируется на языке получателя; без выбора — на русском."""
        await locales.set(1, "en")
        await jobs.add(make_message(telegram_id=1, type=NotificationType.REGISTRATION_CANCELLED))
        await jobs.add(make_message(telegram_id=2, type=NotificationType.REGISTRATION_CANCELLED))

        await worker.run_once()
        await worker.run_once()

        texts = dict(sender.sent)
        assert "has been cancelled" in texts[1]
        assert "отменена" in texts[2]

    async def test_order_follows_priority(
        self, jobs: JobRepository, worker: QueueWorker, sender: FakeSender
    ) -> None:
        """Сначала уходит срочное, потом обычное, потом массовое."""
        await jobs.add(
            make_message(type=NotificationType.BROADCAST, priority=3, payload={"text": "C"})
        )
        await jobs.add(
            make_message(type=NotificationType.BROADCAST, priority=2, payload={"text": "B"})
        )
        await jobs.add(
            make_message(type=NotificationType.BROADCAST, priority=1, payload={"text": "A"})
        )

        while await worker.run_once():
            pass

        assert [text for _, text in sender.sent] == ["A", "B", "C"]

    async def test_scheduled_message_waits_for_its_time(
        self, jobs: JobRepository, worker: QueueWorker, sender: FakeSender
    ) -> None:
        """Событие с будущим временем не отправляется раньше срока."""
        await jobs.add(make_message(send_at=datetime.now(UTC) + timedelta(hours=1)))

        assert await worker.run_once() is False
        assert sender.sent == []


class TestFailures:
    """Ошибки доставки."""

    async def test_temporary_error_is_retried_later(
        self, jobs: JobRepository, worker: QueueWorker, sender: FakeSender
    ) -> None:
        """Временная ошибка откладывает задание: задержка растёт с попытками."""
        message = make_message()
        await jobs.add(message)
        sender.errors = [DeliveryError("Таймаут", retryable=True)]
        before = datetime.now(UTC)

        await worker.run_once()

        (job,) = await jobs.waiting(message.telegram_id)
        assert job.attempts == 1
        assert job.last_error == "Таймаут"
        assert job.run_at >= before + timedelta(seconds=60)
        assert await worker.run_once() is False

    async def test_flood_limit_uses_telegram_delay(
        self, jobs: JobRepository, worker: QueueWorker, sender: FakeSender
    ) -> None:
        """Если Telegram просит подождать, ждём ровно столько."""
        message = make_message()
        await jobs.add(message)
        sender.errors = [DeliveryError("Flood", retryable=True, retry_after=5)]
        before = datetime.now(UTC)

        await worker.run_once()

        (job,) = await jobs.waiting(message.telegram_id)
        assert before + timedelta(seconds=4) <= job.run_at <= before + timedelta(seconds=30)

    async def test_permanent_error_fails_at_once(
        self, jobs: JobRepository, worker: QueueWorker, sender: FakeSender
    ) -> None:
        """Постоянная ошибка (бот заблокирован) не повторяется."""
        message = make_message()
        await jobs.add(message)
        sender.errors = [DeliveryError("Бот заблокирован", retryable=False)]

        await worker.run_once()

        assert await jobs.waiting(message.telegram_id) == []
        job = await jobs.get(1)
        assert job is not None
        assert job.status is JobStatus.FAILED
        assert job.last_error == "Бот заблокирован"

    async def test_attempts_are_limited(
        self, jobs: JobRepository, locales: LocaleRepository, sender: FakeSender
    ) -> None:
        """После последней разрешённой попытки задание закрывается как проваленное."""
        settings = QueueSettings(
            _env_file=None, send_interval=0, calm_period=0.01, max_attempts=3, retry_delay=0
        )
        worker = QueueWorker(jobs, locales, sender, Messages(Translator("Europe/Moscow")), settings)
        await jobs.add(make_message())
        sender.errors = [DeliveryError("Таймаут") for _ in range(3)]

        for _ in range(3):
            await worker.run_once()

        job = await jobs.get(1)
        assert job is not None
        assert job.status is JobStatus.FAILED
        assert job.attempts == 3

    async def test_unexpected_error_is_retried(
        self, jobs: JobRepository, worker: QueueWorker, sender: FakeSender
    ) -> None:
        """Неожиданное исключение не теряет сообщение: оно повторяется позже."""
        message = make_message()
        await jobs.add(message)
        sender.errors = [RuntimeError("сбой")]

        await worker.run_once()

        (job,) = await jobs.waiting(message.telegram_id)
        assert "RuntimeError" in (job.last_error or "")


class TestRun:
    """Фоновый цикл."""

    async def test_loop_sends_what_arrives(
        self, jobs: JobRepository, worker: QueueWorker, sender: FakeSender
    ) -> None:
        """Цикл подхватывает новые события по мере появления."""
        task = asyncio.create_task(worker.run())
        await jobs.add(make_message())
        await wait_until(lambda: len(sender.sent) == 1)
        task.cancel()

        assert len(sender.sent) == 1

    async def test_stuck_jobs_are_restored_on_start(
        self, jobs: JobRepository, worker: QueueWorker, sender: FakeSender
    ) -> None:
        """При запуске задания, прерванные сбоем, возвращаются в очередь и отправляются."""
        await jobs.add(make_message())
        await jobs.claim_next()

        task = asyncio.create_task(worker.run())
        await wait_until(lambda: len(sender.sent) == 1)
        task.cancel()

        assert len(sender.sent) == 1

    async def test_loop_survives_storage_errors(
        self, jobs: JobRepository, worker: QueueWorker, sender: FakeSender
    ) -> None:
        """Сбой хранилища не останавливает цикл."""
        await jobs.add(make_message())
        original = jobs.claim_next
        calls = 0

        async def flaky() -> object:
            nonlocal calls
            calls += 1

            if calls == 1:
                raise ConnectionError("БД недоступна")

            job = await original()

            return job

        with patch.object(jobs, "claim_next", side_effect=flaky):
            task = asyncio.create_task(worker.run())
            await wait_until(lambda: len(sender.sent) == 1)
            task.cancel()

        assert calls >= 2
