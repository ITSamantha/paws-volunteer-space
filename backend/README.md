# Backend

API платформы Paw Volunteer Space: организация мероприятий, запись волонтёров и посещения приютов. Единственный клиент — Telegram-бот (каталог `bot/`).

Стек: Python 3.11+, FastAPI, SQLAlchemy 2 (async, драйвер asyncpg), Alembic, Pydantic 2, PostgreSQL.

## Быстрый старт

Все команды выполняются в каталоге `backend/`.

```bash
uv sync                         # создаёт .venv и ставит зависимости из uv.lock

cp .env.example .env            # затем задайте POSTGRES_PASSWORD и AUTH_BOT_TOKEN (от 32 символов)
docker compose --env-file .env -f ../docker-compose.dev.yml up -d db         # PostgreSQL на 127.0.0.1:5432 (добавьте kafka, если нужны уведомления)
uv run alembic upgrade head    # применить миграции
uv run python -m app.database.seeders    # заполнить справочники (повторно запускать безопасно)
uv run uvicorn app.main:app --reload   # http://127.0.0.1:8000/health
```

## Уведомления боту

Из эндпоинтов API публикует события в Kafka (`KAFKA_IS_ENABLED=true`, топик `KAFKA_NOTIFICATIONS_TOPIC`). Сервис `NotificationService` копит события во время запроса и отправляет их **после** успешного коммита: бот не узнает о том, чего не произошло. Если брокер недоступен, запрос всё равно успешен, ошибка пишется в лог. Событие содержит тип, приоритет (1 — высокий, 2 — обычный, 3 — низкий), данные и время отправки `send_at` (пусто — сразу); очередь, повторы и отправка в Telegram на стороне бота.

## Проверки

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest                        # проверки на реальной БД требуют Docker; без него пропускаются
uv run pytest -m "not integration"   # только быстрые проверки без БД
```

## Работа с миграциями

```bash
uv run alembic revision --autogenerate -m "описание"   # затем ПРОВЕРЬТЕ файл вручную
uv run alembic upgrade head
uv run alembic downgrade -1
```
