import asyncio
from typing import ClassVar

from app.database.seeders.base.seeder import Seeder
from app.database.seeders.event import BonusSeeder, TagSeeder
from app.database.session import Database


class Seeders:
    """Запуск всех сидеров в одной транзакции."""

    ORDER: ClassVar[tuple[type[Seeder], ...]] = (BonusSeeder, TagSeeder)

    @classmethod
    async def run(cls) -> None:
        async with Database.session_factory()() as session, session.begin():
            for seeder in cls.ORDER:
                await seeder().run(session)

        await Database.engine().dispose()

    @classmethod
    def main(cls) -> None:
        asyncio.run(cls.run())
