import asyncio
from collections.abc import Awaitable, Callable


async def wait_until(condition: Callable[[], bool | Awaitable[bool]]) -> None:
    """Ждёт, пока условие не выполнится; за 10 секунд не дождался — проверка падает."""
    async with asyncio.timeout(10):
        while True:
            result = condition()

            if isinstance(result, bool):
                done = result
            else:
                done = await result

            if done:
                return

            await asyncio.sleep(0.05)
