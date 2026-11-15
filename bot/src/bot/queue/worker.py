import asyncio
import logging
from datetime import UTC, datetime, timedelta

from bot.config import QueueSettings
from bot.i18n.repository import LocaleRepository
from bot.i18n.translator import Translator
from bot.messaging.schemas import NotificationType
from bot.queue.models import Job
from bot.queue.repository import JobRepository
from bot.sending.errors import DeliveryError
from bot.sending.messages import Messages
from bot.sending.sender import Sender

logger = logging.getLogger(__name__)


class QueueWorker:
    """Берёт задания из очереди и отправляет их.

    Порядок: высокий приоритет раньше, внутри приоритета — раньше назначенное время. События
    с будущим временем ждут своего часа. Между отправками выдерживается пауза (лимиты Telegram).
    Временная ошибка откладывает задание с растущей задержкой, постоянная или исчерпанные
    попытки закрывают его как проваленное.
    """

    def __init__(
        self,
        jobs: JobRepository,
        locales: LocaleRepository,
        sender: Sender,
        messages: Messages,
        settings: QueueSettings,
    ) -> None:
        """Собирает воркер из очереди, языков, отправителя, шаблонов и настроек."""
        self.__jobs = jobs
        self.__locales = locales
        self.__sender = sender
        self.__messages = messages
        self.__settings = settings

    async def run_once(self) -> bool:
        """Обрабатывает одно готовое задание; False, если очередь пуста."""
        job = await self.__jobs.claim_next()

        if job is None:
            return False

        await self.__process(job)

        return True

    async def run(self) -> None:
        """Бесконечный цикл: при пустой очереди отдыхает, после отправки выдерживает паузу."""
        await self.__jobs.requeue_stuck()

        while True:
            try:
                handled = await self.run_once()
            except Exception:
                logger.exception("Сбой обработки очереди")
                handled = False

            await asyncio.sleep(
                self.__settings.send_interval if handled else self.__settings.calm_period
            )

    async def __process(self, job: Job) -> None:
        """Отправляет сообщение и фиксирует итог."""
        try:
            locale = Translator.normalize(await self.__locales.get(job.telegram_id))
            text = self.__messages.render(NotificationType(job.type), job.payload, locale)
            await self.__sender.send(job.telegram_id, text)
        except DeliveryError as error:
            await self.__handle_failure(job, str(error), error.retryable, error.retry_after)
        except Exception as error:
            logger.exception("Неожиданный сбой отправки задания %s", job.id)
            await self.__handle_failure(job, repr(error), True, None)
        else:
            await self.__jobs.complete(job.id)

    async def __handle_failure(
        self, job: Job, error: str, retryable: bool, retry_after: float | None
    ) -> None:
        """Откладывает задание на повтор или закрывает как проваленное."""
        attempts = job.attempts + 1

        if not retryable or attempts >= self.__settings.max_attempts:
            logger.warning("Задание %s не доставлено: %s", job.id, error)
            await self.__jobs.fail(job.id, error)
            return

        delay = retry_after if retry_after is not None else self.__settings.retry_delay * attempts
        await self.__jobs.retry(job.id, datetime.now(UTC) + timedelta(seconds=delay), error)
