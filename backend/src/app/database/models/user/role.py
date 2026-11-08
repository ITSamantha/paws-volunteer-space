from datetime import datetime

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, PgEnum
from app.database.models.enums import RoleType


class UserRole(Base):
    """Дополнительная роль пользователя."""

    __tablename__ = "user_roles"
    __table_args__ = {"comment": "Дополнительные роли пользователей"}

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Пользователь, которому выдана роль",
    )
    role: Mapped[RoleType] = mapped_column(
        PgEnum.create(RoleType, "role_type"),
        primary_key=True,
        comment="Роль пользователя",
    )
    granted_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        comment="Кто выдал роль",
    )
    granted_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), comment="Дата и время выдачи роли"
    )
