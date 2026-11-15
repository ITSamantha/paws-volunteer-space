import logging
from datetime import datetime
from importlib.resources import files
from importlib.resources.abc import Traversable
from typing import ClassVar
from zoneinfo import ZoneInfo

from babel.dates import format_skeleton, format_time
from fluent.runtime import FluentBundle, FluentResource

logger = logging.getLogger(__name__)


class Translator:
    """Переводы на основе Project Fluent.

    Тексты лежат в locales/<язык>/messages.ftl: там же правила множественного числа и склонения.
    Если в языке нет нужного ключа, берётся текст языка по умолчанию; если нет и там, возвращается
    сам ключ и пишется ошибка в лог: событие не должно застревать в очереди из-за опечатки.
    Даты форматируются через Babel в часовом поясе клуба.
    """

    DEFAULT: ClassVar[str] = "ru"
    SUPPORTED: ClassVar[tuple[str, ...]] = ("ru", "en")
    LOCALES: ClassVar[Traversable] = files("bot.i18n") / "locales"

    def __init__(self, timezone: str, locales: Traversable | None = None) -> None:
        """Загружает переводы всех поддерживаемых языков."""
        self.__zone = ZoneInfo(timezone)
        directory = locales if locales is not None else self.LOCALES
        self.__bundles = {code: self.__load(directory, code) for code in self.SUPPORTED}

    @classmethod
    def normalize(cls, code: str | None) -> str:
        """Язык из кода Telegram: «ru-RU» → «ru»; неизвестный или пустой → язык по умолчанию."""
        language = (code or "").replace("_", "-").split("-")[0].lower()

        return language if language in cls.SUPPORTED else cls.DEFAULT

    def translate(self, locale: str, key: str, **args: str | int | None) -> str:
        """Текст по ключу на нужном языке; значения None заменяются пустой строкой."""
        values = {name: ("" if value is None else value) for name, value in args.items()}

        for code in dict.fromkeys((self.normalize(locale), self.DEFAULT)):
            bundle = self.__bundles[code]

            try:
                message = bundle.get_message(key)
            except KeyError:
                continue

            if message.value is None:
                continue

            text, errors = bundle.format_pattern(message.value, values)

            if errors:
                logger.error("Ошибки перевода %s (%s): %s", key, code, errors)

            return str(text)

        logger.error("Нет перевода для ключа %s", key)

        return key

    def moment(self, locale: str, value: datetime) -> str:
        """Дата и время по-человечески на нужном языке: «5 марта, 10:00»."""
        local = value.astimezone(self.__zone)
        code = self.normalize(locale)
        day = format_skeleton("MMMMd", local, locale=code)

        return f"{day}, {format_time(local, 'HH:mm', locale=code)}"

    @staticmethod
    def __load(directory: Traversable, code: str) -> FluentBundle:
        """Читает файл переводов языка."""
        source = (directory / code / "messages.ftl").read_text(encoding="utf-8")
        bundle = FluentBundle([code], use_isolating=False)
        bundle.add_resource(FluentResource(source))

        return bundle
