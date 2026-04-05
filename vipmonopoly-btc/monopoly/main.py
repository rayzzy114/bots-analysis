import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from db.init_db import init_db
from db.settings import init_settings_db
from config import BOT_TOKEN, PARSE_MODE
from routers import get_routers

async def main():
    await init_db()
    await init_settings_db()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=PARSE_MODE))
    dp = Dispatcher(storage=MemoryStorage())

    bot_info = await bot.get_me()

    print(f"Успешно запущен: @{bot_info.username}")

    for router in get_routers():
        dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)

    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())