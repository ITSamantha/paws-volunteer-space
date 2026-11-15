from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_jobs",
        sa.Column("id", sa.Integer(), nullable=False, comment="Внутренний идентификатор"),
        sa.Column(
            "message_id",
            sa.String(length=64),
            nullable=False,
            comment="Идентификатор события от API; защита от повторов",
        ),
        sa.Column(
            "telegram_id", sa.BigInteger(), nullable=False, comment="Получатель (Telegram ID)"
        ),
        sa.Column("type", sa.String(length=64), nullable=False, comment="Тип события"),
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            comment="Приоритет: 1 — высокий, 2 — обычный, 3 — низкий",
        ),
        sa.Column(
            "event_id", sa.Integer(), nullable=True, comment="Мероприятие, о котором событие"
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Данные для подстановки в текст",
        ),
        sa.Column(
            "key",
            sa.String(length=255),
            nullable=True,
            comment="Ключ замены: новое событие вытесняет ещё не отправленное с тем же",
        ),
        sa.Column("status", sa.String(length=16), nullable=False, comment="Состояние задания"),
        sa.Column(
            "run_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Не отправлять раньше этого момента",
        ),
        sa.Column(
            "attempts", sa.Integer(), nullable=False, comment="Сколько попыток отправки было"
        ),
        sa.Column("last_error", sa.String(), nullable=True, comment="Текст последней ошибки"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Когда событие получено",
        ),
        sa.Column(
            "finished_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Когда задание завершено",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_jobs")),
        sa.UniqueConstraint("message_id", name=op.f("uq_notification_jobs_message_id")),
        comment="Очередь доставки уведомлений бота",
    )
    op.create_index(
        "ix_notification_jobs_status_priority_run_at",
        "notification_jobs",
        ["status", "priority", "run_at"],
        unique=False,
    )
    op.create_index(
        "ix_notification_jobs_telegram_id_key",
        "notification_jobs",
        ["telegram_id", "key"],
        unique=False,
    )
    op.create_index(
        "ix_notification_jobs_telegram_id_event_id",
        "notification_jobs",
        ["telegram_id", "event_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_notification_jobs_telegram_id_event_id", table_name="notification_jobs")
    op.drop_index("ix_notification_jobs_telegram_id_key", table_name="notification_jobs")
    op.drop_index("ix_notification_jobs_status_priority_run_at", table_name="notification_jobs")
    op.drop_table("notification_jobs")
