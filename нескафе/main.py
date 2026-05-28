"""Точка входа клона @NeskafeEx_bot."""

from __future__ import annotations

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.handlers import account, admin, common, exchange, start
from app.runtime import AppContext


async def _inject_ctx(handler, event, data):
    """Middleware: прокидывает AppContext во все хендлеры как ctx."""
    data["ctx"] = data["dispatcher"]["ctx"]
    return await handler(event, data)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    token = os.environ["BOT_TOKEN"]

    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp["ctx"] = AppContext.from_env()

    dp.message.middleware(_inject_ctx)
    dp.callback_query.middleware(_inject_ctx)

    # admin — первым, чтобы /admin не перехватывался пользовательскими хендлерами
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(exchange.router)
    dp.include_router(account.router)
    dp.include_router(common.router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
