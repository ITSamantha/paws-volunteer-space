from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, MetaData
from sqlalchemy.orm import DeclarativeBase

from app.database.rules import NamingConvention


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NamingConvention.PATTERNS)
    type_annotation_map = {datetime: DateTime(timezone=True)}


class PgEnum:
    @staticmethod
    def create(enum_cls: type[StrEnum], name: str) -> Enum:
        return Enum(
            enum_cls,
            name=name,
            native_enum=True,
            validate_strings=True,
            values_callable=lambda cls: [member.value for member in cls],
        )
