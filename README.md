# Paw Volunteer Space

Платформа для координации волонтёров клуба «Лапки помощи» ITMO: организация мероприятий, запись волонтёров и посещения приютов.

Стек: Python 3.11+, FastAPI, SQLAlchemy 2 (async, драйвер asyncpg), Alembic, Pydantic 2, PostgreSQL.

## Быстрый старт

```bash
uv sync                         # создаёт .venv и ставит зависимости из uv.lock

cp .env.example .env            # затем задайте POSTGRES_PASSWORD и AUTH_BOT_TOKEN (от 32 символов)
docker compose -f docker-compose.dev.yml up -d db         # PostgreSQL на 127.0.0.1:5432
uv run alembic upgrade head    # применить миграции
uv run python -m app.database.seeders    # заполнить справочники (повторно запускать безопасно)
uv run uvicorn app.main:app --reload   # http://127.0.0.1:8000/health
```

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
