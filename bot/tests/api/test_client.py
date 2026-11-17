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

    async def test_events_asks_for_planned_visits(self) -> None:
        """Список запрашивает только запланированные мероприятия, не больше восьми."""

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.params["status"] == "planned"
            assert request.url.params["limit"] == "8"
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": 4,
                            "title": "Выезд",
                            "starts_at": "2030-03-05T07:00:00Z",
                            "location": "Метро",
                            "occupied": 1,
                            "capacity": 5,
                        }
                    ],
                    "total": 1,
                    "limit": 8,
                    "offset": 0,
                },
            )

        page = await client(httpx.MockTransport(handler)).events(7)

        assert page.total == 1
        assert page.items[0].id == 4
        assert page.items[0].title == "Выезд"

    async def test_event_loads_one_card(self) -> None:
        """Карточка запрашивается по ID мероприятия."""

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/events/4"
            return httpx.Response(
                200,
                json={
                    "id": 4,
                    "title": "Выезд",
                    "starts_at": "2030-03-05T07:00:00Z",
                    "location": "Метро",
                    "capacity": 5,
                    "occupied": 1,
                    "status": "planned",
                },
            )

        card = await client(httpx.MockTransport(handler)).event(7, 4)

        assert card.title == "Выезд"
        assert card.location == "Метро"

    async def test_register_posts_the_current_user(self) -> None:
        """Запись уходит POST-ом на мероприятие от имени пользователя."""

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "POST"
            assert request.url.path == "/api/events/4/registrations"
            assert request.headers["x-telegram-id"] == "7"
            body = {
                "id": 9,
                "event_id": 4,
                "status": "pending",
                "created_at": "2030-01-01T00:00:00Z",
            }

            return httpx.Response(201, json=body)

        result = await client(httpx.MockTransport(handler)).register(7, 4)

        assert result.status == "pending"
