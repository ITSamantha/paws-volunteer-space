from typing import Annotated, ClassVar
from urllib.parse import urlsplit

from pydantic import AfterValidator, Field, StringConstraints


class FieldValidators:
    """Проверки и преобразования значений полей."""

    VK_HOSTS: ClassVar[frozenset[str]] = frozenset(
        {"vk.com", "www.vk.com", "m.vk.com", "vk.ru", "www.vk.ru", "m.vk.ru"}
    )

    TELEGRAM_HOSTS: ClassVar[frozenset[str]] = frozenset({"t.me", "telegram.me", "telegram.dog"})

    @classmethod
    def vk_link(cls, value: str) -> str:
        """Проверяет, что ссылка ведёт на профиль ВКонтакте."""
        parts = urlsplit(value)

        if parts.scheme not in {"http", "https"} or parts.hostname not in cls.VK_HOSTS:
            raise ValueError("ссылка должна вести на профиль ВКонтакте (vk.com или vk.ru)")

        if len(parts.path.strip("/")) == 0:
            raise ValueError("в ссылке не указан профиль")

        return value

    @staticmethod
    def http_url(value: str) -> str:
        """Проверяет, что значение — ссылка http или https."""
        parts = urlsplit(value)

        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise ValueError("нужна ссылка, начинающаяся с http:// или https://")

        return value

    @classmethod
    def telegram_link(cls, value: str) -> str:
        """Проверяет, что ссылка ведёт в Telegram."""
        cls.http_url(value)

        if urlsplit(value).hostname not in cls.TELEGRAM_HOSTS:
            raise ValueError("ссылка должна вести в Telegram (t.me)")

        return value

    @staticmethod
    def tag_title(value: str) -> str:
        """Убирает ведущий # из названия тега: теги хранятся без него."""
        title = value.removeprefix("#").strip()

        if not title:
            raise ValueError("название тега не может быть пустым")

        return title

    @staticmethod
    def strip_at(value: str) -> str:
        """Убирает ведущий @ из имени пользователя Telegram."""
        return value.removeprefix("@")


Phone = Annotated[str, StringConstraints(pattern=r"^\+[0-9]{10,15}$")]
FullName = Annotated[str, StringConstraints(min_length=1, max_length=255)]
TelegramUsername = Annotated[
    str,
    StringConstraints(pattern=r"^@?[A-Za-z0-9_]{5,32}$"),
    AfterValidator(FieldValidators.strip_at),
]
IsuId = Annotated[str, StringConstraints(pattern=r"^[0-9]{1,16}$")]
VolunteerId = Annotated[str, StringConstraints(min_length=1, max_length=64)]
VkLink = Annotated[str, StringConstraints(max_length=255), AfterValidator(FieldValidators.vk_link)]
Title = Annotated[str, StringConstraints(min_length=1, max_length=255)]
TagTitle = Annotated[
    str, StringConstraints(min_length=1, max_length=255), AfterValidator(FieldValidators.tag_title)
]
Capacity = Annotated[int, Field(gt=0, le=1000)]
HttpLink = Annotated[
    str, StringConstraints(max_length=500), AfterValidator(FieldValidators.http_url)
]
TelegramLink = Annotated[
    str, StringConstraints(max_length=500), AfterValidator(FieldValidators.telegram_link)
]
Description = Annotated[str, StringConstraints(min_length=1, max_length=5000)]
Location = Annotated[str, StringConstraints(min_length=1, max_length=500)]
Address = Annotated[str, StringConstraints(min_length=1, max_length=500)]
Instructions = Annotated[str, StringConstraints(min_length=1, max_length=5000)]
ContactValue = Annotated[str, StringConstraints(min_length=1, max_length=500)]
Comment = Annotated[str, StringConstraints(min_length=1, max_length=2000)]
