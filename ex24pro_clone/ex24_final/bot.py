from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import TelegramObject, Update

from config import BOT_TOKEN, banned_users
from runtime_state import admin_router, rate_service


class BanMiddleware(BaseMiddleware):
    """Silently drop all updates from banned users."""

    async def __call__(self, handler, event: TelegramObject, data: dict):
        if isinstance(event, Update):
            user = None
            if event.message and event.message.from_user:
                user = event.message.from_user
            elif event.callback_query and event.callback_query.from_user:
                user = event.callback_query.from_user
            if user and user.id in banned_users:
                return  # silently ignore
        return await handler(event, data)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is empty — set it in .env")
        sys.exit(1)

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.outer_middleware(BanMiddleware())

    # Admin router (handles /admin and admin:* callbacks)
    if admin_router is not None:
        dp.include_router(admin_router)

    # Application routers
    from handlers.livechat import router as livechat_router
    from handlers.menu import router as menu_router
    from handlers.start import router as start_router

    dp.include_router(start_router)
    dp.include_router(menu_router)
    dp.include_router(livechat_router)

    # Pre-fetch rates on startup
    await rate_service.get_rates(force=True)

    logger.info("Bot started")
    await dp.start_polling(bot, drop_pending_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
