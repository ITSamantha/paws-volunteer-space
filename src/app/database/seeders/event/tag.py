from app.database.models import Tag
from app.database.seeders.base.titles import TitleSeeder


class TagSeeder(TitleSeeder):
    model = Tag
    filename = "tags.json"
