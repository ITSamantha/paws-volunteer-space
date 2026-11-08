from sqlalchemy import BigInteger, CheckConstraint, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, PgEnum
from app.database.mixins import SoftDeleteMixin, TimestampMixin
from app.database.models.enums import UserStatus
from app.database.models.user.role import UserRole


class User(TimestampMixin, SoftDeleteMixin, Base):
    """Пользователь бота."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "status <> 'blocked' OR (comment IS NOT NULL AND btrim(comment) <> '')",
            name="blocked_requires_comment",
        ),
        CheckConstraint(r"phone ~ '^\+[0-9]{10,15}$'", name="phone_format"),
        {"comment": "Пользователи бота"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, comment="Внутренний идентификатор")
    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        comment="Идентификатор в Telegram (в отличие от telegram_username, не меняется)",
    )
    isu_id: Mapped[str | None] = mapped_column(
        String(16), unique=True, comment="Номер ИСУ (необязательно)"
    )
    volunteer_id: Mapped[str | None] = mapped_column(
        String(64), unique=True, comment="Идентификатор волонтёра на добро.рф (необязательно)"
    )
    full_name: Mapped[str | None] = mapped_column(
        String(255), comment="ФИО, указанное волонтёром; NULL, пока не заполнено"
    )
    phone: Mapped[str] = mapped_column(String(16), comment="Номер телефона")
    telegram_username: Mapped[str | None] = mapped_column(
        String(64), comment="@username в Telegram; может отсутствовать или меняться"
    )
    vk_link: Mapped[str | None] = mapped_column(
        String(255), comment="Ссылка на профиль во ВКонтакте (необязательно)"
    )

    status: Mapped[UserStatus] = mapped_column(
        PgEnum.create(UserStatus, "user_status"),
        server_default=UserStatus.ACTIVE.value,
        comment="Статус в системе",
    )
    comment: Mapped[str | None] = mapped_column(
        comment="Комментарий (например, причина блокировки); обязателен при статусе blocked"
    )

    has_notifications_enabled: Mapped[bool] = mapped_column(
        server_default=text("true"),
        comment="Включены ли у пользователя необязательные уведомления и рассылки",
    )
    is_data_processing_allowed: Mapped[bool] = mapped_column(
        server_default=text("false"),
        comment="Дал ли пользователь согласие на обработку персональных данных",
    )

    roles: Mapped[list[UserRole]] = relationship(
        foreign_keys="UserRole.user_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )
