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
            return response.json()

        code = "http_error"

        try:
            payload = response.json()
        except ValueError:
            payload = None

        if isinstance(payload, dict) and isinstance(payload.get("code"), str):
            code = payload["code"]

        raise ApiError(response.status_code, code)
