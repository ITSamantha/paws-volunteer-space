from app.database.models import Bonus
from app.database.seeders.base.titles import TitleSeeder


class BonusSeeder(TitleSeeder):
    """Заполняет справочник бонусов."""

    model = Bonus
    filename = "bonuses.json"
