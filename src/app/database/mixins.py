from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        sort_order=1000,
        comment="Дата и время создания записи",
    )


class TimestampMixin(CreatedAtMixin):
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        sort_order=1001,
        comment="Дата и время последнего изменения записи",
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(
        sort_order=1002,
        comment="Дата и время удаления записи; NULL — запись активна",
    )
