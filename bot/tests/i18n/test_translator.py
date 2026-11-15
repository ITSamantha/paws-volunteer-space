import logging
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fluent.syntax import FluentParser
from fluent.syntax.ast import Junk

from bot.i18n.translator import Translator
from bot.messaging.schemas import NotificationType


def locales_dir(tmp_path: Path, ru: str, en: str) -> Path:
    for code, source in (("ru", ru), ("en", en)):
        (tmp_path / code).mkdir()
        (tmp_path / code / "messages.ftl").write_text(source, encoding="utf-8")

    return tmp_path


def message_ids(code: str) -> set[str]:
    source = (Translator.LOCALES / code / "messages.ftl").read_text(encoding="utf-8")

    return set(re.findall(r"^([a-z][a-z0-9-]*) =", source, flags=re.MULTILINE))


class TestNormalize:
    """Определение языка по коду Telegram."""

    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            ("ru", "ru"),
            ("ru-RU", "ru"),
            ("en", "en"),
            ("en-US", "en"),
            ("EN_gb", "en"),
            ("de", "ru"),
            ("", "ru"),
            (None, "ru"),
        ],
    )
    def test_normalize(self, code: str | None, expected: str) -> None:
        """Регион отбрасывается, неизвестный или пустой код заменяется языком по умолчанию."""
        assert Translator.normalize(code) == expected


class TestTranslate:
    """Переводы."""

    def test_arguments_are_substituted(self) -> None:
        """Значения подставляются в текст."""
        text = Translator("Europe/Moscow").translate(
            "ru", "notification-reminder", title="Х", when=""
        )

        assert text.startswith("Напоминаем: «Х»")

    def test_none_becomes_empty_string(self) -> None:
        """Пустое значение превращается в пустую строку, а не в «None»."""
        text = Translator("Europe/Moscow").translate(
            "ru", "notification-reminder", title="Х", when=None
        )

        assert "None" not in text

    def test_missing_key_in_language_falls_back_to_default(self, tmp_path: Path) -> None:
        """Если в языке нет ключа, берётся текст языка по умолчанию."""
        directory = locales_dir(
            tmp_path, ru="hello = Привет\nonly-ru = Только русский", en="hello = Hi"
        )
        translator = Translator("Europe/Moscow", directory)

        assert translator.translate("en", "hello") == "Hi"
        assert translator.translate("en", "only-ru") == "Только русский"

    def test_message_without_value_falls_back_to_default(self, tmp_path: Path) -> None:
        """Сообщение с одними атрибутами (без текста) считается отсутствующим."""
        directory = locales_dir(
            tmp_path, ru="hello = Привет\nattrs-only =\n    .title = Заголовок", en="hello = Hi"
        )
        translator = Translator("Europe/Moscow", directory)

        assert translator.translate("en", "attrs-only") == "attrs-only"

    def test_missing_key_everywhere_returns_the_key(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Если ключа нет нигде, возвращается он сам и пишется ошибка: сообщение не теряется."""
        translator = Translator("Europe/Moscow", locales_dir(tmp_path, "a = 1", "a = 1"))

        with caplog.at_level(logging.ERROR):
            text = translator.translate("ru", "nope")

        assert text == "nope"
        assert "nope" in caplog.text

    def test_formatting_errors_are_logged(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Нехватка аргумента не ломает перевод, но попадает в лог."""
        directory = locales_dir(tmp_path, "hello = Привет, { $name }", "hello = Hi, { $name }")
        translator = Translator("Europe/Moscow", directory)

        with caplog.at_level(logging.ERROR):
            text = translator.translate("ru", "hello")

        assert "Привет" in text
        assert "Ошибки перевода" in caplog.text

    def test_russian_plural_forms(self, tmp_path: Path) -> None:
        """Русские формы множественного числа: 1 место, 3 места, 5 мест, 21 место."""
        ru = """spots = { $n ->
    [one] Осталось { $n } место
    [few] Осталось { $n } места
   *[many] Осталось { $n } мест
}"""
        translator = Translator("Europe/Moscow", locales_dir(tmp_path, ru, "spots = x"))

        forms = {n: translator.translate("ru", "spots", n=n) for n in (1, 2, 5, 11, 21, 25)}

        assert forms == {
            1: "Осталось 1 место",
            2: "Осталось 2 места",
            5: "Осталось 5 мест",
            11: "Осталось 11 мест",
            21: "Осталось 21 место",
            25: "Осталось 25 мест",
        }

    def test_english_plural_forms(self, tmp_path: Path) -> None:
        """Английские формы множественного числа."""
        en = """spots = { $n ->
    [one] { $n } spot left
   *[other] { $n } spots left
}"""
        translator = Translator("Europe/Moscow", locales_dir(tmp_path, "spots = x", en))

        assert translator.translate("en", "spots", n=1) == "1 spot left"
        assert translator.translate("en", "spots", n=3) == "3 spots left"


class TestMoment:
    """Даты и время."""

    MOMENT = datetime(2030, 3, 5, 7, 0, tzinfo=UTC)

    def test_russian(self) -> None:
        """По-русски с названием месяца в родительном падеже."""
        assert Translator("Europe/Moscow").moment("ru", self.MOMENT) == "5 марта, 10:00"

    def test_english(self) -> None:
        """По-английски."""
        assert Translator("Europe/Moscow").moment("en", self.MOMENT) == "March 5, 10:00"

    def test_timezone_comes_from_settings(self) -> None:
        """Часовой пояс берётся из настроек."""
        assert Translator("Asia/Yekaterinburg").moment("ru", self.MOMENT) == "5 марта, 12:00"

    def test_unknown_language_uses_default(self) -> None:
        """Неизвестный язык форматируется как язык по умолчанию."""
        assert Translator("Europe/Moscow").moment("xx", self.MOMENT) == "5 марта, 10:00"


class TestLocaleFiles:
    """Файлы переводов."""

    def test_languages_have_the_same_keys(self) -> None:
        """Во всех языках одинаковый набор ключей: ни один перевод не потерян."""
        reference = message_ids(Translator.DEFAULT)

        for code in Translator.SUPPORTED:
            assert message_ids(code) == reference, code

    @pytest.mark.parametrize("notification_type", list(NotificationType))
    def test_every_notification_type_is_translated(
        self, notification_type: NotificationType
    ) -> None:
        """Для каждого типа события есть ключ перевода."""
        key = "notification-" + notification_type.value.replace("_", "-")

        for code in Translator.SUPPORTED:
            assert key in message_ids(code)

    def test_files_parse_without_junk(self) -> None:
        """Файлы разбираются без ошибок разметки."""
        for code in Translator.SUPPORTED:
            source = (Translator.LOCALES / code / "messages.ftl").read_text(encoding="utf-8")
            resource = FluentParser().parse(source)

            assert not [entry for entry in resource.body if isinstance(entry, Junk)], code
