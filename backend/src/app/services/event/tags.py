from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Tag
from app.repositories.base.titles import TitleRepository
from app.services.base.titles import TitleService


class TagService(TitleService[Tag]):
    """Справочник тегов мероприятий."""

    def __init__(self, session: AsyncSession) -> None:
        """Работает в переданной сессии."""
        repository = TitleRepository(
            session, Tag, "uq_tags_title_lower", "Тег с таким названием уже есть"
        )

        super().__init__(session, repository, "Тег")
