from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_locales",
        sa.Column(
            "menu_message_id",
            sa.BigInteger(),
            nullable=True,
            comment="Сообщение с меню; предыдущее удаляется, уведомления не трогаются",
        ),
    )


def downgrade() -> None:
    op.drop_column("user_locales", "menu_message_id")
