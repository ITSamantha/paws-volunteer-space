from typing import ClassVar


class NamingConvention:
    """Соглашение об именах индексов и ограничений БД.

    Явные имена делают миграции Alembic детерминированными: ограничение можно
    изменить или удалить по имени, а не по имени, придуманному самой СУБД.

    Ключи: ix — индексы, uq — уникальные ограничения, ck — check, fk — внешние
    ключи, pk — первичные ключи. Для check-ограничений имя (constraint_name)
    задаётся в модели.
    """

    PATTERNS: ClassVar[dict[str, str]] = {
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
