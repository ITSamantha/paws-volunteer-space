import httpx
import pytest

from bot.api.client import ApiClient, ApiError


def client(handler: httpx.MockTransport) -> ApiClient:
    http = httpx.AsyncClient(transport=handler, base_url="http://api")

    return ApiClient("token-with-thirty-two-characters", http)


class TestApiClient:
    """Запросы к API от имени пользователя."""

    async def test_profile_sends_the_bot_token_and_telegram_id(self) -> None:
        """Каждый запрос несёт токен бота и Telegram ID пользователя."""

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["authorization"] == "Bearer token-with-thirty-two-characters"
            assert request.headers["x-telegram-id"] == "7"
            return httpx.Response(200, json={"id": 3, "roles": ["organizer"], "status": "active"})

        profile = await client(httpx.MockTransport(handler)).profile(7)

        assert profile is not None
        assert profile.id == 3
        assert profile.roles == ["organizer"]

    async def test_missing_user_is_none(self) -> None:
        """Незарегистрированный пользователь — это отсутствие профиля, а не ошибка."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"code": "not_found"})

        profile = await client(httpx.MockTransport(handler)).profile(7)

        assert profile is None

    async def test_other_errors_keep_the_api_code(self) -> None:
        """Остальные ответы API становятся ошибкой с их кодом."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(403, json={"code": "forbidden"})

        with pytest.raises(ApiError) as error:
            await client(httpx.MockTransport(handler)).profile(7)

        assert error.value.status_code == 403
        assert error.value.code == "forbidden"
