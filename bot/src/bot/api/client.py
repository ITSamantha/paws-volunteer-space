from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict


class ApiError(Exception):
    """API ответил ошибкой, с которой бот может что-то сделать."""

    def __init__(self, status_code: int, code: str) -> None:
        """Сохраняет код ответа и код ошибки из тела."""
        super().__init__(code)
        self.status_code = status_code
        self.code = code


class EventLine(BaseModel):
    """Мероприятие в списке бота."""

    model_config = ConfigDict(extra="ignore")

    id: int
    title: str
    starts_at: datetime
    location: str | None = None
    occupied: int = 0
    capacity: int


class EventPlace(BaseModel):
    """Место выезда: приют или точка встречи."""

    model_config = ConfigDict(extra="ignore")

    title: str | None = None
    address: str | None = None


class EventCard(BaseModel):
    """Карточка мероприятия для сообщения бота."""

    model_config = ConfigDict(extra="ignore")

    id: int
    title: str
    starts_at: datetime
    location: str | None = None
    shelter: EventPlace | None = None
    capacity: int
    occupied: int = 0
    description: str | None = None
    instructions: str | None = None
    status: str


class EventPage(BaseModel):
    """Страница мероприятий."""

    model_config = ConfigDict(extra="ignore")

    items: list[EventLine]
    total: int


class RegistrationResult(BaseModel):
    """Ответ на запись: место получено, ждёт одобрения или в листе ожидания."""

    model_config = ConfigDict(extra="ignore")

    id: int
    event_id: int
    status: str


class Profile(BaseModel):
    """Профиль пользователя, которого обслуживает бот."""

    model_config = ConfigDict(extra="ignore")

    id: int
    roles: list[str] = []
    status: str


class ApiClient:
    """Запросы к API от имени пользователя Telegram."""

    def __init__(self, token: str, client: httpx.AsyncClient) -> None:
        """Токен бота один на все запросы, Telegram ID передаётся в каждом."""
        self.__token = token
        self.__client = client

    async def profile(self, telegram_id: int) -> Profile | None:
        """Профиль пользователя. None, если он ещё не зарегистрирован."""
        response = await self.request("GET", f"/api/users/by-telegram/{telegram_id}", telegram_id)

        if response.status_code == 404:
            return None

        body = self.__json(response)

        return Profile.model_validate(body)

    async def events(self, telegram_id: int) -> EventPage:
        """Ближайшие запланированные мероприятия."""
        response = await self.request(
            "GET",
            "/api/events",
            telegram_id,
            params={"status": "planned", "limit": 8},
        )

        page = EventPage.model_validate(self.__json(response))

        return page

    async def event(self, telegram_id: int, event_id: int) -> EventCard:
        """Карточка одного мероприятия."""
        response = await self.request("GET", f"/api/events/{event_id}", telegram_id)

        card = EventCard.model_validate(self.__json(response))

        return card

    async def register(self, telegram_id: int, event_id: int) -> RegistrationResult:
        """Записывает пользователя на мероприятие."""
        response = await self.request("POST", f"/api/events/{event_id}/registrations", telegram_id)

        result = RegistrationResult.model_validate(self.__json(response))

        return result

    async def request(
        self, method: str, path: str, telegram_id: int, **kwargs: Any
    ) -> httpx.Response:
        """Выполняет запрос с токеном бота и заголовком X-Telegram-Id."""
        response = await self.__client.request(
            method,
            path,
            headers={
                "Authorization": f"Bearer {self.__token}",
                "X-Telegram-Id": str(telegram_id),
            },
            **kwargs,
        )

        return response

    @staticmethod
    def __json(response: httpx.Response) -> Any:
        """Тело успешного ответа или ошибка API."""
        if response.is_success:
            body = response.json()

            return body

        code = "http_error"

        try:
            payload = response.json()
        except ValueError:
            payload = None

        if isinstance(payload, dict) and isinstance(payload.get("code"), str):
            code = payload["code"]

        error = ApiError(response.status_code, code)

        raise error
