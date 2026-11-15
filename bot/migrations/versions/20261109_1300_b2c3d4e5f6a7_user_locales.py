from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_locales",
        sa.Column(
            "telegram_id",
            sa.BigInteger(),
            autoincrement=False,
            nullable=False,
            comment="Пользователь (Telegram ID)",
        ),
        sa.Column(
            "locale", sa.String(length=8), nullable=False, comment="Код языка, например ru или en"
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Когда язык выбран или изменён",
        ),
        sa.PrimaryKeyConstraint("telegram_id", name=op.f("pk_user_locales")),
        comment="Языки пользователей бота",
    )


def downgrade() -> None:
    op.drop_table("user_locales")
