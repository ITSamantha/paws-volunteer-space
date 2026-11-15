import pytest

from bot.i18n.translator import Translator
from bot.messaging.schemas import NotificationType
from bot.sending.messages import Messages

PAYLOAD = {
    "title": "Выезд в приют",
    "starts_at": "2030-03-05T07:00:00+00:00",
    "reason": "Плохая погода",
    "full_name": "Иван Иванов",
}


@pytest.fixture
def messages() -> Messages:
    return Messages(Translator("Europe/Moscow"))


class TestRender:
    """Тексты уведомлений."""

    @pytest.mark.parametrize("locale", Translator.SUPPORTED)
    @pytest.mark.parametrize("notification_type", list(NotificationType))
    def test_every_type_has_a_text_in_every_language(
        self, messages: Messages, notification_type: NotificationType, locale: str
    ) -> None:
        """Для каждого типа события есть непустой текст на каждом языке, это не ключ."""
        payload = {**PAYLOAD, "text": "Всем привет", "changed": ["starts_at"]}

        text = messages.render(notification_type, payload, locale)

        assert text.strip()
        assert not text.startswith("notification-")

    @pytest.mark.parametrize("locale", Translator.SUPPORTED)
    @pytest.mark.parametrize("notification_type", list(NotificationType))
    def test_missing_payload_does_not_break_rendering(
        self, messages: Messages, notification_type: NotificationType, locale: str
    ) -> None:
        """Даже без данных текст формируется: событие не должно застревать в очереди."""
        messages.render(notification_type, None, locale)
        messages.render(notification_type, {}, locale)

    def test_russian_text(self, messages: Messages) -> None:
        """Русский текст с датой по Москве: 07:00 UTC — это 10:00."""
        text = messages.render(NotificationType.REGISTRATION_CONFIRMED, PAYLOAD, "ru")

        assert text.startswith("Вы записаны на «Выезд в приют» (5 марта, 10:00).")

    def test_english_text(self, messages: Messages) -> None:
        """Английский текст с английским названием месяца."""
        text = messages.render(NotificationType.REGISTRATION_CONFIRMED, PAYLOAD, "en")

        assert text.startswith("You are registered for “Выезд в приют” (March 5, 10:00).")

    def test_unknown_language_falls_back_to_russian(self, messages: Messages) -> None:
        """Неизвестный язык заменяется языком по умолчанию."""
        text = messages.render(NotificationType.REGISTRATION_CANCELLED, PAYLOAD, "xx")

        assert "отменена" in text

    @pytest.mark.parametrize("month", range(1, 13))
    def test_every_month_is_localized(self, messages: Messages, month: int) -> None:
        """Месяцы подставляются на обоих языках."""
        payload = {"title": "Выезд", "starts_at": f"2030-{month:02d}-15T12:00:00+03:00"}

        ru = messages.render(NotificationType.REMINDER, payload, "ru")
        en = messages.render(NotificationType.REMINDER, payload, "en")

        assert "15 " in ru
        assert "15" in en

    def test_user_text_is_escaped(self, messages: Messages) -> None:
        """Пользовательский текст экранируется: нельзя вставить HTML-разметку."""
        text = messages.render(
            NotificationType.EVENT_CANCELLED,
            {"title": "<b>Выезд</b>", "reason": "<a href='x'>ссылка</a>"},
            "ru",
        )

        assert "<b>" not in text
        assert "&lt;b&gt;Выезд&lt;/b&gt;" in text
        assert "<a href" not in text

    def test_comment_is_used_when_there_is_no_reason(self, messages: Messages) -> None:
        """Отказ организатора передаёт причину в поле comment."""
        text = messages.render(
            NotificationType.REGISTRATION_REJECTED,
            {"title": "Выезд", "comment": "Нет мест"},
            "ru",
        )

        assert "Нет мест" in text

    def test_changes_are_described_in_words(self, messages: Messages) -> None:
        """Что изменилось, перечисляется человеческим языком на языке получателя."""
        payload = {"title": "Выезд", "changed": ["starts_at", "location", "unknown_field"]}

        ru = messages.render(NotificationType.EVENT_CHANGED, payload, "ru")
        en = messages.render(NotificationType.EVENT_CHANGED, payload, "en")

        assert "время начала, место встречи, unknown_field" in ru
        assert "start time, meeting point, unknown_field" in en

    def test_changes_fallback(self, messages: Messages) -> None:
        """Если перечня изменений нет, отправляет посмотреть карточку."""
        text = messages.render(NotificationType.EVENT_CHANGED, {"title": "Выезд"}, "ru")

        assert "карточке" in text

    def test_unexpected_changed_value_is_ignored(self, messages: Messages) -> None:
        """Если changed пришло не списком, сообщение всё равно формируется."""
        text = messages.render(
            NotificationType.EVENT_CHANGED, {"title": "Выезд", "changed": "starts_at"}, "ru"
        )

        assert "карточке" in text

    def test_broadcast_is_the_authors_text(self, messages: Messages) -> None:
        """Рассылка — это текст автора."""
        text = messages.render(NotificationType.BROADCAST, {"text": "Всем привет"}, "ru")

        assert text == "Всем привет"

    def test_organizer_messages_name_the_volunteer(self, messages: Messages) -> None:
        """Организатору сообщается, кто записался или отменил запись."""
        for notification_type in (
            NotificationType.ORGANIZER_NEW_REGISTRATION,
            NotificationType.ORGANIZER_APPROVAL_REQUESTED,
            NotificationType.ORGANIZER_CANCELLATION,
        ):
            assert "Иван Иванов" in messages.render(notification_type, PAYLOAD, "ru")

    def test_fallbacks_are_translated(self, messages: Messages) -> None:
        """Без названия и имени подставляются общие слова на языке получателя."""
        assert "мероприятие" in messages.render(NotificationType.REGISTRATION_PENDING, {}, "ru")
        assert "the event" in messages.render(NotificationType.REGISTRATION_PENDING, {}, "en")
        assert "волонтёр" in messages.render(NotificationType.ORGANIZER_NEW_REGISTRATION, {}, "ru")
        assert "a volunteer" in messages.render(
            NotificationType.ORGANIZER_NEW_REGISTRATION, {}, "en"
        )
