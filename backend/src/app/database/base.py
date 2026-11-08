from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, MetaData
from sqlalchemy.orm import DeclarativeBase

from app.database.rules import NamingConvention


class Base(DeclarativeBase):
    """Базовый класс всех моделей; даты хранятся с часовым поясом."""

    metadata = MetaData(naming_convention=NamingConvention.PATTERNS)
    type_annotation_map = {datetime: DateTime(timezone=True)}


class PgEnum:
    """Фабрика нативных enum PostgreSQL."""

    @staticmethod
    def create(enum_cls: type[StrEnum], name: str) -> Enum:
        """Создаёт enum, который хранит в БД значения (value), а не имена членов."""
        return Enum(
            enum_cls,
            name=name,
            native_enum=True,
            validate_strings=True,
            values_callable=lambda cls: [member.value for member in cls],
        )
