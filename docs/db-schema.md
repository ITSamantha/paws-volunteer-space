# Схема БД: Paw Volunteer Space

```mermaid
erDiagram
    users ||--o{ user_roles : "user_id"
    users |o--o{ user_roles : "granted_by"
    shelters ||--o{ shelter_contacts : "shelter_id"
    shelters |o--o{ events : "shelter_id"
    users ||--o{ events : "created_by"
    events ||--o{ registrations : "event_id"
    events ||--o{ event_bonuses : "event_id"
    bonuses ||--o{ event_bonuses : "bonus_id"
    events ||--o{ event_tags : "event_id"
    tags ||--o{ event_tags : "tag_id"
    users |o--o{ bonuses : "created_by"
    users |o--o{ tags : "created_by"
    users ||--o{ registrations : "user_id"
    users |o--o{ registrations : "decided_by"
    users ||--o{ broadcasts : "author_id"
    events |o--o{ broadcasts : "event_id"
    users ||--o{ notifications : "user_id"
    events |o--o{ notifications : "event_id"
    broadcasts |o--o{ notifications : "broadcast_id"

    users {
        int id PK
        bigint telegram_id UK
        varchar(16) isu_id UK "необяз."
        varchar(64) volunteer_id UK "необяз."
        varchar(255) full_name "необяз."
        varchar(16) phone
        varchar(64) telegram_username "необяз."
        varchar(255) vk_link "необяз."
        user_status status "active | blocked"
        text comment "необяз."
        bool has_notifications_enabled
        bool is_data_processing_allowed
        timestamptz created_at
        timestamptz updated_at
        timestamptz deleted_at "необяз."
    }

    user_roles {
        int user_id PK, FK
        role_type role PK "organizer | smm | admin"
        int granted_by FK "необяз."
        timestamptz granted_at
    }

    shelters {
        int id PK
        varchar(255) title
        varchar(500) address
        text instructions "необяз."
        bool is_approval_required
        timestamptz created_at
        timestamptz updated_at
        timestamptz deleted_at "необяз."
    }

    shelter_contacts {
        int id PK
        int shelter_id FK
        contact_type type "phone | email | website | vk | telegram | whatsapp | other"
        varchar(500) value
    }

    events {
        int id PK
        varchar(255) title
        text description "необяз."
        timestamptz starts_at
        timestamptz ends_at "необяз."
        int shelter_id FK "необяз."
        varchar(500) location "необяз."
        int capacity
        bool is_approval_required
        event_status status "planned | cancelled | completed"
        text cancellation_reason "необяз."
        text instructions "необяз."
        text comment "необяз."
        varchar(500) event_link "необяз."
        varchar(500) telegram_chat_link "необяз."
        int created_by FK
        timestamptz created_at
        timestamptz updated_at
    }

    bonuses {
        int id PK
        varchar(255) title
        int created_by FK "необяз."
        timestamptz created_at
        timestamptz deleted_at "необяз."
    }

    event_bonuses {
        int event_id PK, FK
        int bonus_id PK, FK
    }

    tags {
        int id PK
        varchar(255) title
        int created_by FK "необяз."
        timestamptz created_at
        timestamptz deleted_at "необяз."
    }

    event_tags {
        int event_id PK, FK
        int tag_id PK, FK
    }

    registrations {
        int id PK
        int event_id FK
        int user_id FK
        registration_status status "registered | pending | rejected | cancelled | waitlisted | attended | absent"
        timestamptz cancelled_at "необяз."
        text cancellation_reason "необяз."
        int decided_by FK "необяз."
        timestamptz decided_at "необяз."
        text decision_comment "необяз."
        timestamptz created_at
    }

    broadcasts {
        int id PK
        int author_id FK
        text text
        broadcast_audience audience "all | announcements_subscribers | event_participants"
        int event_id FK "необяз."
        broadcast_status status "draft | queued | sent"
        timestamptz sent_at "необяз."
        timestamptz created_at
    }

    notifications {
        int id PK
        int user_id FK
        notification_type type "registration_confirmed | registration_pending | registration_approved | registration_rejected | registration_waitlisted | spot_freed | registration_cancelled | event_changed | event_cancelled | reminder | new_event | organizer_new_registration | organizer_approval_requested | organizer_cancellation | user_blocked | broadcast"
        int event_id FK "необяз."
        int broadcast_id FK "необяз."
        jsonb payload "необяз."
        varchar(255) dedup_key "необяз."
        notification_status status "pending | sent | failed"
        timestamptz scheduled_at
        timestamptz sent_at "необяз."
        int attempts
        text last_error "необяз."
        timestamptz created_at
    }
```

## Ограничения и индексы

- `users`: `status <> 'blocked' OR (comment IS NOT NULL AND btrim(comment) <> '')` (`ck_users_blocked_requires_comment`)
- `users`: `phone ~ '^\+[0-9]{10,15}$'` (`ck_users_phone_format`)
- `shelter_contacts`: `btrim(value) <> ''` (`ck_shelter_contacts_value_not_empty`)
- `shelter_contacts`: уникальна комбинация (shelter_id, type, value)
- `events`: `capacity > 0` (`ck_events_capacity_positive`)
- `events`: `ends_at IS NULL OR ends_at > starts_at` (`ck_events_ends_after_start`)
- `events`: `status <> 'cancelled' OR (cancellation_reason IS NOT NULL AND btrim(cancellation_reason) <> '')` (`ck_events_cancelled_requires_reason`)
- `events`: `location IS NOT NULL OR shelter_id IS NOT NULL` (`ck_events_has_place`)
- индекс `ix_events_status_starts_at` по (status, starts_at)
- `bonuses`, `tags`: `title = btrim(title) AND title <> ''` (`ck_bonuses_title_trimmed`, `ck_tags_title_trimmed`)
- уникальные индексы `uq_bonuses_title_lower`, `uq_tags_title_lower` по `lower(title)` среди неудалённых записей (без учёта регистра)
- индекс `ix_event_bonuses_bonus_id` по (bonus_id)
- индекс `ix_event_tags_tag_id` по (tag_id)
- `registrations`: `status <> 'cancelled' OR (cancellation_reason IS NOT NULL AND btrim(cancellation_reason) <> '')` (`ck_registrations_cancelled_requires_reason`)
- `registrations`: `(status = 'cancelled') = (cancelled_at IS NOT NULL)` (`ck_registrations_cancelled_at_matches_status`)
- `registrations`: `(decided_by IS NULL) = (decided_at IS NULL)` (`ck_registrations_decision_author_matches_time`)
- `registrations`: `status <> 'rejected' OR (decided_by IS NOT NULL AND decision_comment IS NOT NULL AND btrim(decision_comment) <> '')` (`ck_registrations_rejected_requires_decision`)
- `registrations`: уникальна комбинация (event_id, user_id)
- индекс `ix_registrations_user_id` по (user_id)
- индекс `ix_registrations_event_id_status` по (event_id, status)
- `broadcasts`: `(audience = 'event_participants') = (event_id IS NOT NULL)` (`ck_broadcasts_event_matches_audience`)
- индекс `ix_broadcasts_author_id` по (author_id)
- индекс `ix_notifications_broadcast_id` по (broadcast_id)
- индекс `ix_notifications_user_id` по (user_id)
- уникальный индекс `uq_notifications_user_id_dedup_key` по (user_id, dedup_key) где `dedup_key IS NOT NULL`
- индекс `ix_notifications_pending_scheduled_at` по (scheduled_at) где `status = 'pending'`

## Начальные данные

Заполняются сидерами из JSON (`src/app/database/seeders/data/`), не миграциями:
`uv run python -m app.database.seeders`. Повторный запуск безопасен.

- `bonuses`: ПГАС, Часы на добро.рф
- `tags`: Выезд, Собаки

## Правила, которые живут в БД вне моделей

- Роли `admin` и `organizer` может выдать только администратор. Правило реализовано
  триггером `trg_user_roles_check_granter` в миграции. Исключение: самовыдача роли
  `admin`, пока в таблице нет ни одного администратора.
- Решение по заявке (`registrations.decided_by`) может принять только ответственный
  организатор мероприятия (`events.created_by`). Правило реализовано триггером
  `trg_registrations_check_decider` в миграции.
