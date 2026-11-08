from app.database.models import Tag
from app.database.seeders.base.titles import TitleSeeder


class TagSeeder(TitleSeeder):
    """Заполняет справочник тегов."""

    model = Tag
    filename = "tags.json"
