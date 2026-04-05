import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from db.init_db import init_db
from config import BOT_TOKEN, PARSE_MODE, RATE_UPDATE_INTERVAL
from routers import get_routers

from utils.exchange_rates import exchange_rates


async def update_rates_periodically():
    while True:
        try:
            await exchange_rates.update_rates()
        except Exception as e:
            print(f"Ошибка обновления курсов: {e}")
        
        await asyncio.sleep(RATE_UPDATE_INTERVAL)

async def main():
    await init_db()
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=PARSE_MODE))
    dp = Dispatcher(storage=MemoryStorage())

    bot_info = await bot.get_me()
    print("Первичное обновление курсов...")
    await exchange_rates.update_rates()
    print(f"Успешно запущен: @{bot_info.username}")
    asyncio.create_task(update_rates_periodically())

    for router in get_routers():
        dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)

    await dp.start_polling(bot)
    
if __name__ == '__main__':
    asyncio.run(main())
