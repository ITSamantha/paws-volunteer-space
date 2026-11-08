from typing import Annotated, ClassVar
from urllib.parse import urlsplit

from pydantic import AfterValidator, StringConstraints


class FieldValidators:
    """Проверки и преобразования значений полей."""

    VK_HOSTS: ClassVar[frozenset[str]] = frozenset(
        {"vk.com", "www.vk.com", "m.vk.com", "vk.ru", "www.vk.ru", "m.vk.ru"}
    )

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
Comment = Annotated[str, StringConstraints(min_length=1, max_length=2000)]
