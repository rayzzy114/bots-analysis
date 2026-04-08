import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError
from aiogram.fsm.storage.memory import MemoryStorage

from src.admin_panel import build_admin_components
from src.cfg import TOKEN
from src.handlers import router

dp = Dispatcher(storage=MemoryStorage())
logger = logging.getLogger(__name__)


import httpx


async def run_bot() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    base_dir = Path(__file__).resolve().parent

    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
        _, admin_router = build_admin_components(base_dir, client=client)
        session = AiohttpSession(timeout=20.0)
        bot = Bot(
            token=TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            session=session,
        )
        dp.include_router(admin_router)
        dp.include_router(router)
        logger.info("Initializing bot before polling")
        try:
            await bot.delete_webhook(drop_pending_updates=True, request_timeout=5)
        except TelegramNetworkError as exc:
            logger.warning("delete_webhook network error: %s. Continuing startup.", exc)

        logger.info("Bot polling started")
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run_bot())
