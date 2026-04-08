import asyncio

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, PARSE_MODE
from db.init_db import init_db
from db.settings import init_settings_db
from routers import get_routers


def parse_amount(text: str) -> float | None:
    """Безопасный парсинг суммы с учетом запятых и пробелов."""
    try:
        return float(text.replace(',', '.').replace(' ', ''))
    except (ValueError, TypeError, AttributeError):
        return None


async def main():
    dp = Dispatcher(storage=MemoryStorage())
    async with aiohttp.ClientSession() as session:
        dp["session"] = session
        await init_db()
        await init_settings_db()
        bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=PARSE_MODE))

        bot_info = await bot.get_me()

        print(f"Успешно запущен: @{bot_info.username}")

        for router in get_routers():
            dp.include_router(router)

        await bot.delete_webhook(drop_pending_updates=True)

        await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
