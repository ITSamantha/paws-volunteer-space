from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import BigInteger, DateTime, Enum, Index, MetaData, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Базовый класс моделей бота."""

    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )
    type_annotation_map = {datetime: DateTime(timezone=True)}


class JobStatus(StrEnum):
    """Состояние задания в очереди."""

    WAITING = "waiting"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class Job(Base):
    """Задание на отправку одного сообщения."""

    __tablename__ = "notification_jobs"
    __table_args__ = (
        Index("ix_notification_jobs_status_priority_run_at", "status", "priority", "run_at"),
        Index("ix_notification_jobs_telegram_id_key", "telegram_id", "key"),
        Index("ix_notification_jobs_telegram_id_event_id", "telegram_id", "event_id"),
        {"comment": "Очередь доставки уведомлений бота"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, comment="Внутренний идентификатор")
    message_id: Mapped[str] = mapped_column(
        String(64), unique=True, comment="Идентификатор события от API; защита от повторов"
    )
    telegram_id: Mapped[int] = mapped_column(BigInteger, comment="Получатель (Telegram ID)")
    type: Mapped[str] = mapped_column(String(64), comment="Тип события")
    priority: Mapped[int] = mapped_column(comment="Приоритет: 1 — высокий, 2 — обычный, 3 — низкий")
    event_id: Mapped[int | None] = mapped_column(comment="Мероприятие, о котором событие")
    payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, comment="Данные для подстановки в текст"
    )
    key: Mapped[str | None] = mapped_column(
        String(255), comment="Ключ замены: новое событие вытесняет ещё не отправленное с тем же"
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(
            JobStatus,
            native_enum=False,
            length=16,
            validate_strings=True,
            values_callable=lambda cls: [member.value for member in cls],
        ),
        default=JobStatus.WAITING,
        comment="Состояние задания",
    )
    run_at: Mapped[datetime] = mapped_column(comment="Не отправлять раньше этого момента")
    attempts: Mapped[int] = mapped_column(default=0, comment="Сколько попыток отправки было")
    last_error: Mapped[str | None] = mapped_column(comment="Текст последней ошибки")
    created_at: Mapped[datetime] = mapped_column(comment="Когда событие получено")
    finished_at: Mapped[datetime | None] = mapped_column(comment="Когда задание завершено")


class UserLocale(Base):
    """Язык, на котором бот общается с пользователем."""

    __tablename__ = "user_locales"
    __table_args__ = {"comment": "Языки пользователей бота"}

    telegram_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, comment="Пользователь (Telegram ID)"
    )
    locale: Mapped[str] = mapped_column(String(8), comment="Код языка, например ru или en")
    menu_message_id: Mapped[int | None] = mapped_column(
        BigInteger, comment="Сообщение с меню; предыдущее удаляется, уведомления не трогаются"
    )
    updated_at: Mapped[datetime] = mapped_column(comment="Когда язык выбран или изменён")
