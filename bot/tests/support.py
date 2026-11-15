import asyncio
from collections.abc import Awaitable, Callable


async def wait_until(condition: Callable[[], bool | Awaitable[bool]]) -> None:
    """Ждёт, пока условие не выполнится; за 15 секунд не дождался — проверка падает."""
    async with asyncio.timeout(15):
        while True:
            result = condition()
            done = result if isinstance(result, bool) else await result

            if done:
                return

            await asyncio.sleep(0.05)
