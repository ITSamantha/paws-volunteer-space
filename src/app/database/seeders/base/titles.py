import json
from typing import ClassVar

from pydantic import TypeAdapter
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Bonus, Tag
from app.database.seeders.base.seeder import Seeder


class TitleSeeder(Seeder):
    """Заполнение справочника, в котором у записи только название."""

    model: ClassVar[type[Bonus] | type[Tag]]
    filename: ClassVar[str]

    @classmethod
    def titles(cls) -> list[str]:
        """Читает названия из JSON-файла."""
        content = (cls.DATA_DIRECTORY / cls.filename).read_text(encoding="utf-8")

        titles = TypeAdapter(list[str]).validate_python(json.loads(content))

        return titles

    async def run(self, session: AsyncSession) -> None:
        """Добавляет отсутствующие названия, существующие не трогает."""
        statement = (
            insert(self.model)
            .values([{"title": title} for title in self.titles()])
            .on_conflict_do_nothing()
        )

        await session.execute(statement)
