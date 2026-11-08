from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "70739494c91f"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CHECK_GRANTER_FUNCTION = """CREATE FUNCTION check_user_role_granter() RETURNS trigger AS $$
BEGIN
    IF NEW.role IN ('admin', 'organizer') THEN
        IF EXISTS (
            SELECT 1 FROM user_roles WHERE user_id = NEW.granted_by AND role = 'admin'
        ) THEN
            RETURN NEW;
        END IF;
        IF NEW.role = 'admin'
            AND NEW.granted_by = NEW.user_id
            AND NOT EXISTS (SELECT 1 FROM user_roles WHERE role = 'admin') THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'Роли admin и organizer может выдать только администратор'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql"""

CHECK_GRANTER_TRIGGER = """CREATE TRIGGER trg_user_roles_check_granter
BEFORE INSERT OR UPDATE OF role, granted_by ON user_roles
FOR EACH ROW EXECUTE FUNCTION check_user_role_granter()"""


def upgrade() -> None:
    op.create_table(
        "shelters",
        sa.Column("id", sa.Integer(), nullable=False, comment="Внутренний идентификатор"),
        sa.Column("title", sa.String(length=255), nullable=False, comment="Название приюта"),
        sa.Column("address", sa.String(length=500), nullable=False, comment="Адрес приюта"),
        sa.Column(
            "instructions",
            sa.String(),
            nullable=True,
            comment="Стандартные требования приюта (сменная одежда, ограничения и т. п.)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата и время создания записи",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата и время последнего изменения записи",
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Дата и время удаления записи; NULL — запись активна",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shelters")),
        comment="Справочник приютов",
    )
    op.create_table(
        "shelter_contacts",
        sa.Column("id", sa.Integer(), nullable=False, comment="Внутренний идентификатор"),
        sa.Column("shelter_id", sa.Integer(), nullable=False, comment="Приют"),
        sa.Column(
            "type",
            sa.Enum(
                "phone",
                "email",
                "website",
                "vk",
                "telegram",
                "whatsapp",
                "other",
                name="contact_type",
            ),
            nullable=False,
            comment="Тип контакта",
        ),
        sa.Column("value", sa.String(length=500), nullable=False, comment="Значение контакта"),
        sa.CheckConstraint("btrim(value) <> ''", name=op.f("ck_shelter_contacts_value_not_empty")),
        sa.ForeignKeyConstraint(
            ["shelter_id"],
            ["shelters.id"],
            name=op.f("fk_shelter_contacts_shelter_id_shelters"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shelter_contacts")),
        sa.UniqueConstraint(
            "shelter_id", "type", "value", name=op.f("uq_shelter_contacts_shelter_id_type_value")
        ),
        comment="Контакты приютов",
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False, comment="Внутренний идентификатор"),
        sa.Column(
            "telegram_id",
            sa.BigInteger(),
            nullable=False,
            comment="Идентификатор в Telegram (в отличие от telegram_username, не меняется)",
        ),
        sa.Column(
            "isu_id",
            sa.String(length=16),
            nullable=True,
            comment="Номер ИСУ (необязательно)",
        ),
        sa.Column(
            "volunteer_id",
            sa.String(length=64),
            nullable=True,
            comment="Идентификатор волонтёра на добро.рф (необязательно)",
        ),
        sa.Column(
            "full_name",
            sa.String(length=255),
            nullable=True,
            comment="ФИО, указанное волонтёром; NULL, пока не заполнено",
        ),
        sa.Column("phone", sa.String(length=16), nullable=False, comment="Номер телефона"),
        sa.Column(
            "telegram_username",
            sa.String(length=64),
            nullable=True,
            comment="@username в Telegram; может отсутствовать или меняться",
        ),
        sa.Column(
            "vk_link",
            sa.String(length=255),
            nullable=True,
            comment="Ссылка на профиль во ВКонтакте (необязательно)",
        ),
        sa.Column(
            "status",
            sa.Enum("active", "blocked", name="user_status"),
            server_default="active",
            nullable=False,
            comment="Статус в системе",
        ),
        sa.Column(
            "comment",
            sa.String(),
            nullable=True,
            comment="Комментарий (например, причина блокировки); обязателен при статусе blocked",
        ),
        sa.Column(
            "has_notifications_enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
            comment="Включены ли у пользователя необязательные уведомления и рассылки",
        ),
        sa.Column(
            "is_data_processing_allowed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="Дал ли пользователь согласие на обработку персональных данных",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата и время создания записи",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата и время последнего изменения записи",
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Дата и время удаления записи; NULL — запись активна",
        ),
        sa.CheckConstraint(
            "status <> 'blocked' OR (comment IS NOT NULL AND btrim(comment) <> '')",
            name=op.f("ck_users_blocked_requires_comment"),
        ),
        sa.CheckConstraint(r"phone ~ '^\+[0-9]{10,15}$'", name=op.f("ck_users_phone_format")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("volunteer_id", name=op.f("uq_users_volunteer_id")),
        sa.UniqueConstraint("isu_id", name=op.f("uq_users_isu_id")),
        sa.UniqueConstraint("telegram_id", name=op.f("uq_users_telegram_id")),
        comment="Пользователи бота",
    )
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), nullable=False, comment="Внутренний идентификатор"),
        sa.Column("title", sa.String(length=255), nullable=False, comment="Название мероприятия"),
        sa.Column(
            "description", sa.String(), nullable=True, comment="Описание и формат активности"
        ),
        sa.Column(
            "starts_at", sa.DateTime(timezone=True), nullable=False, comment="Дата и время начала"
        ),
        sa.Column(
            "ends_at", sa.DateTime(timezone=True), nullable=True, comment="Дата и время окончания"
        ),
        sa.Column(
            "shelter_id",
            sa.Integer(),
            nullable=True,
            comment="Приют, в котором проходит мероприятие (если применимо)",
        ),
        sa.Column(
            "location",
            sa.String(length=500),
            nullable=True,
            comment="Место встречи; если не указано, используется адрес приюта",
        ),
        sa.Column(
            "capacity",
            sa.Integer(),
            nullable=False,
            comment="Лимит участников; должен быть больше нуля",
        ),
        sa.Column(
            "is_approval_required",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="Нужно ли организатору одобрять записи; иначе запись подтверждается автоматически",
        ),
        sa.Column(
            "status",
            sa.Enum("planned", "cancelled", "completed", name="event_status"),
            server_default="planned",
            nullable=False,
            comment="Статус мероприятия",
        ),
        sa.Column(
            "instructions",
            sa.String(),
            nullable=True,
            comment="Что взять с собой, требования приюта, прочая инструкция",
        ),
        sa.Column("comment", sa.String(), nullable=True, comment="Прочая информация о мероприятии"),
        sa.Column(
            "event_link",
            sa.String(length=500),
            nullable=True,
            comment="Ссылка на мероприятие на добро.рф (необязательно)",
        ),
        sa.Column(
            "telegram_chat_link",
            sa.String(length=500),
            nullable=True,
            comment="Ссылка на Telegram-чат участников; показывается только подтверждённым",
        ),
        sa.Column(
            "created_by", sa.Integer(), nullable=False, comment="Организатор, создавший мероприятие"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата и время создания записи",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата и время последнего изменения записи",
        ),
        sa.CheckConstraint("capacity > 0", name=op.f("ck_events_capacity_positive")),
        sa.CheckConstraint(
            "ends_at IS NULL OR ends_at > starts_at", name=op.f("ck_events_ends_after_start")
        ),
        sa.CheckConstraint(
            "location IS NOT NULL OR shelter_id IS NOT NULL", name=op.f("ck_events_has_place")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_events_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["shelter_id"],
            ["shelters.id"],
            name=op.f("fk_events_shelter_id_shelters"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_events")),
        comment="Волонтёрские мероприятия и поездки в приюты",
    )
    op.create_index("ix_events_status_starts_at", "events", ["status", "starts_at"], unique=False)
    op.create_table(
        "bonuses",
        sa.Column("id", sa.Integer(), nullable=False, comment="Внутренний идентификатор"),
        sa.Column("title", sa.String(length=255), nullable=False, comment="Название бонуса"),
        sa.Column(
            "created_by",
            sa.Integer(),
            nullable=True,
            comment="Кто добавил бонус; NULL — бонус из начального справочника",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата и время создания записи",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_bonuses_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "title = btrim(title) AND title <> ''", name=op.f("ck_bonuses_title_trimmed")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bonuses")),
        comment="Справочник бонусов за участие в мероприятиях",
    )
    op.create_index(
        "uq_bonuses_title_lower", "bonuses", [sa.literal_column("lower(title)")], unique=True
    )
    op.create_table(
        "event_bonuses",
        sa.Column("event_id", sa.Integer(), nullable=False, comment="Мероприятие"),
        sa.Column("bonus_id", sa.Integer(), nullable=False, comment="Бонус"),
        sa.ForeignKeyConstraint(
            ["bonus_id"],
            ["bonuses.id"],
            name=op.f("fk_event_bonuses_bonus_id_bonuses"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name=op.f("fk_event_bonuses_event_id_events"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("event_id", "bonus_id", name=op.f("pk_event_bonuses")),
        comment="Бонусы, которые получают участники мероприятия",
    )
    op.create_index(op.f("ix_event_bonuses_bonus_id"), "event_bonuses", ["bonus_id"], unique=False)
    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), nullable=False, comment="Внутренний идентификатор"),
        sa.Column("title", sa.String(length=255), nullable=False, comment="Название тега (без #)"),
        sa.Column(
            "created_by",
            sa.Integer(),
            nullable=True,
            comment="Кто добавил тег; NULL — тег из начального справочника",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата и время создания записи",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_tags_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "title = btrim(title) AND title <> ''", name=op.f("ck_tags_title_trimmed")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tags")),
        comment="Справочник тегов мероприятий",
    )
    op.create_index("uq_tags_title_lower", "tags", [sa.literal_column("lower(title)")], unique=True)
    op.create_table(
        "event_tags",
        sa.Column("event_id", sa.Integer(), nullable=False, comment="Мероприятие"),
        sa.Column("tag_id", sa.Integer(), nullable=False, comment="Тег"),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["tags.id"],
            name=op.f("fk_event_tags_tag_id_tags"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name=op.f("fk_event_tags_event_id_events"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("event_id", "tag_id", name=op.f("pk_event_tags")),
        comment="Теги мероприятия",
    )
    op.create_index(op.f("ix_event_tags_tag_id"), "event_tags", ["tag_id"], unique=False)
    op.create_table(
        "user_roles",
        sa.Column(
            "user_id", sa.Integer(), nullable=False, comment="Пользователь, которому выдана роль"
        ),
        sa.Column(
            "role",
            sa.Enum("organizer", "smm", "admin", name="role_type"),
            nullable=False,
            comment="Роль пользователя",
        ),
        sa.Column("granted_by", sa.Integer(), nullable=True, comment="Кто выдал роль"),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата и время выдачи роли",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by"],
            ["users.id"],
            name=op.f("fk_user_roles_granted_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_roles_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "role", name=op.f("pk_user_roles")),
        comment="Дополнительные роли пользователей",
    )
    op.execute(CHECK_GRANTER_FUNCTION)
    op.execute(CHECK_GRANTER_TRIGGER)
    op.create_table(
        "broadcasts",
        sa.Column("id", sa.Integer(), nullable=False, comment="Внутренний идентификатор"),
        sa.Column("author_id", sa.Integer(), nullable=False, comment="Автор рассылки"),
        sa.Column("text", sa.String(), nullable=False, comment="Текст рассылки"),
        sa.Column(
            "audience",
            sa.Enum(
                "all", "announcements_subscribers", "event_participants", name="broadcast_audience"
            ),
            nullable=False,
            comment="Аудитория рассылки",
        ),
        sa.Column(
            "event_id",
            sa.Integer(),
            nullable=True,
            comment="Мероприятие, участникам которого адресована рассылка",
        ),
        sa.Column(
            "status",
            sa.Enum("draft", "queued", "sent", name="broadcast_status"),
            server_default="draft",
            nullable=False,
            comment="Статус рассылки",
        ),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Дата и время отправки рассылки",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата и время создания записи",
        ),
        sa.CheckConstraint(
            "(audience = 'event_participants') = (event_id IS NOT NULL)",
            name=op.f("ck_broadcasts_event_matches_audience"),
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            name=op.f("fk_broadcasts_author_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name=op.f("fk_broadcasts_event_id_events"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_broadcasts")),
        comment="Рассылки",
    )
    op.create_index(op.f("ix_broadcasts_author_id"), "broadcasts", ["author_id"], unique=False)
    op.create_table(
        "registrations",
        sa.Column("id", sa.Integer(), nullable=False, comment="Внутренний идентификатор"),
        sa.Column("event_id", sa.Integer(), nullable=False, comment="Мероприятие"),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="Волонтёр"),
        sa.Column(
            "status",
            sa.Enum(
                "registered",
                "pending",
                "rejected",
                "cancelled",
                "waitlisted",
                "attended",
                "absent",
                name="registration_status",
            ),
            server_default="registered",
            nullable=False,
            comment="Статус записи",
        ),
        sa.Column(
            "cancelled_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Дата и время отмены записи; NULL, если не отменялась",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата и время создания записи",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name=op.f("fk_registrations_event_id_events"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_registrations_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_registrations")),
        sa.UniqueConstraint("event_id", "user_id", name="uq_registrations_event_id_user_id"),
        comment="Записи волонтёров на мероприятия",
    )
    op.create_index(
        "ix_registrations_event_id_status", "registrations", ["event_id", "status"], unique=False
    )
    op.create_index(op.f("ix_registrations_user_id"), "registrations", ["user_id"], unique=False)
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False, comment="Внутренний идентификатор"),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="Получатель"),
        sa.Column(
            "type",
            sa.Enum(
                "registration_confirmed",
                "event_changed",
                "event_cancelled",
                "reminder",
                "new_event",
                "organizer_new_registration",
                "organizer_cancellation",
                "broadcast",
                name="notification_type",
            ),
            nullable=False,
            comment="Тип уведомления",
        ),
        sa.Column(
            "event_id", sa.Integer(), nullable=True, comment="Мероприятие, о котором уведомление"
        ),
        sa.Column(
            "broadcast_id",
            sa.Integer(),
            nullable=True,
            comment="Рассылка, из которой создано уведомление",
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Данные для подстановки в шаблон сообщения",
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "sent", "failed", name="notification_status"),
            server_default="pending",
            nullable=False,
            comment="Статус отправки",
        ),
        sa.Column(
            "scheduled_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата и время, раньше которых не отправлять (для напоминаний)",
        ),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Дата и время фактической отправки",
        ),
        sa.Column(
            "attempts",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
            comment="Сколько попыток отправки уже было",
        ),
        sa.Column(
            "last_error", sa.String(), nullable=True, comment="Текст последней ошибки отправки"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата и время создания записи",
        ),
        sa.ForeignKeyConstraint(
            ["broadcast_id"],
            ["broadcasts.id"],
            name=op.f("fk_notifications_broadcast_id_broadcasts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name=op.f("fk_notifications_event_id_events"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notifications_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
        comment="Очередь уведомлений пользователям (outbox)",
    )
    op.create_index(
        op.f("ix_notifications_broadcast_id"), "notifications", ["broadcast_id"], unique=False
    )
    op.create_index(
        "ix_notifications_pending_scheduled_at",
        "notifications",
        ["scheduled_at"],
        unique=False,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(op.f("ix_notifications_user_id"), "notifications", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_notifications_user_id"), table_name="notifications")
    op.drop_index(
        "ix_notifications_pending_scheduled_at",
        table_name="notifications",
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.drop_index(op.f("ix_notifications_broadcast_id"), table_name="notifications")
    op.drop_table("notifications")
    op.drop_index(op.f("ix_registrations_user_id"), table_name="registrations")
    op.drop_index("ix_registrations_event_id_status", table_name="registrations")
    op.drop_table("registrations")
    op.drop_index(op.f("ix_broadcasts_author_id"), table_name="broadcasts")
    op.drop_table("broadcasts")
    op.execute("DROP TRIGGER trg_user_roles_check_granter ON user_roles")
    op.execute("DROP FUNCTION check_user_role_granter()")
    op.drop_table("user_roles")
    op.drop_index(op.f("ix_event_tags_tag_id"), table_name="event_tags")
    op.drop_table("event_tags")
    op.drop_index("uq_tags_title_lower", table_name="tags")
    op.drop_table("tags")
    op.drop_index(op.f("ix_event_bonuses_bonus_id"), table_name="event_bonuses")
    op.drop_table("event_bonuses")
    op.drop_index("uq_bonuses_title_lower", table_name="bonuses")
    op.drop_table("bonuses")
    op.drop_index("ix_events_status_starts_at", table_name="events")
    op.drop_table("events")
    op.drop_table("users")
    op.drop_table("shelter_contacts")
    op.drop_table("shelters")

    for enum_name in (
        "contact_type",
        "notification_status",
        "notification_type",
        "broadcast_status",
        "broadcast_audience",
        "registration_status",
        "event_status",
        "role_type",
        "user_status",
    ):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
