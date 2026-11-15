import html
from datetime import datetime
from typing import Any

from bot.i18n.translator import Translator
from bot.messaging.schemas import NotificationType


class Messages:
    """Тексты уведомлений: берёт переводы по типу события и подставляет данные."""

    FIELDS = ("starts_at", "ends_at", "location", "shelter_id", "instructions")

    def __init__(self, translator: Translator) -> None:
        """Работает через переводчик."""
        self.__translator = translator

    def render(
        self, notification_type: NotificationType, payload: dict[str, Any] | None, locale: str
    ) -> str:
        """Текст сообщения на языке получателя в формате HTML."""
        data = payload or {}
        translate = self.__translator.translate
        key = "notification-" + notification_type.value.replace("_", "-")

        return translate(
            locale,
            key,
            title=self.__text(data.get("title")) or translate(locale, "fallback-title"),
            reason=self.__text(data.get("reason") or data.get("comment"))
            or translate(locale, "fallback-reason"),
            person=self.__text(data.get("full_name")) or translate(locale, "fallback-person"),
            text=self.__text(data.get("text")),
            when=self.__when(data.get("starts_at"), locale),
            changes=self.__changes(data.get("changed"), locale),
        )

    def __when(self, value: object, locale: str) -> str:
        """« (5 марта, 10:00)» для времени начала или пустая строка."""
        if not isinstance(value, str):
            return ""

        moment = self.__translator.moment(locale, datetime.fromisoformat(value))

        return self.__translator.translate(locale, "time-suffix", moment=moment)

    def __changes(self, changed: object, locale: str) -> str:
        """Что изменилось, человеческим языком."""
        translate = self.__translator.translate
        items = changed if isinstance(changed, list) else []
        names = [
            translate(locale, "field-" + str(item).replace("_", "-"))
            if str(item) in self.FIELDS
            else html.escape(str(item))
            for item in items
        ]

        return ", ".join(names) if names else translate(locale, "fallback-changes")

    @staticmethod
    def __text(value: object) -> str:
        """Безопасный для HTML текст из данных события."""
        return html.escape(str(value)) if value else ""
