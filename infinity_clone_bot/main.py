import asyncio
from pathlib import Path

import httpx
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import AppConfig
from app.context import AppContext
from app.handlers.admin import build_admin_router
from app.handlers.buy import build_buy_router
from app.handlers.common import build_common_router
from app.handlers.flow import build_flow_router
from app.rates import RateService
from app.storage import SettingsStore, UsersStore


async def run() -> None:
    base_dir = Path(__file__).resolve().parent
    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    config = AppConfig.from_env(base_dir)
    settings = SettingsStore(
        path=data_dir / "settings.json",
        default_commission=config.default_commission_percent,
        env_links=config.links,
    )
    users = UsersStore(path=data_dir / "users.json")

    async with httpx.AsyncClient() as client:
        rates = RateService(client=client)
        rates.start()

        ctx = AppContext(
            settings=settings,
            users=users,
            rates=rates,
            admin_ids=config.admin_ids,
            env_path=base_dir / ".env",
            bot_username=config.links.get("bot_username", "infinity_clone_bot"),
        )

        bot = Bot(
            token=config.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )

        dp = Dispatcher()
        dp.include_router(build_buy_router(ctx))
        dp.include_router(build_flow_router(ctx))
        dp.include_router(build_admin_router(ctx))
        dp.include_router(build_common_router(ctx))

        print("Bot started")
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run())
