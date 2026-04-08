import asyncio

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import TelegramObject, Update

from cfg.base import TOKEN
from src.handlers.admin.orders import admin_orders_router
from src.handlers.admin.payment_methods import admin_router
from src.handlers.transaction.buy import buy_router
from src.handlers.transaction.sale import sale_router
from src.handlers.user.start import start_router
from src.utils.ban import banned_users

dp = Dispatcher(storage=MemoryStorage())


class BanMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        if isinstance(event, Update):
            user = None
            if event.message and event.message.from_user:
                user = event.message.from_user
            elif event.callback_query and event.callback_query.from_user:
                user = event.callback_query.from_user
            if user and user.id in banned_users:
                return
        return await handler(event, data)


async def main() -> None:
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp.update.outer_middleware(BanMiddleware())
    dp.include_router(start_router)
    dp.include_router(buy_router)
    dp.include_router(sale_router)
    dp.include_router(admin_router)
    dp.include_router(admin_orders_router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
