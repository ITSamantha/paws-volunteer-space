from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Bonus
from app.repositories.base.titles import TitleRepository
from app.services.base.titles import TitleService


class BonusService(TitleService[Bonus]):
    """Справочник бонусов за участие."""

    def __init__(self, session: AsyncSession) -> None:
        """Работает в переданной сессии."""
        repository = TitleRepository(
            session, Bonus, "uq_bonuses_title_lower", "Бонус с таким названием уже есть"
        )

        super().__init__(session, repository, "Бонус")
