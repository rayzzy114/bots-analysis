import asyncio
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import AppConfig
from app.constants import COINS, FALLBACK_RATES
from app.context import AppContext
from app.handlers.admin import build_admin_router
from app.handlers.buy import build_buy_router
from app.handlers.common import build_common_router
from app.handlers.sell import build_sell_router
from app.rates import RateService
from app.storage import SettingsStore, UsersStore


async def run() -> None:
    base_dir = Path(__file__).resolve().parent
    data_dir = base_dir / "data"
    assets_dir = base_dir / "assets"
    data_dir.mkdir(parents=True, exist_ok=True)

    config = AppConfig.from_env(base_dir)
    settings = SettingsStore(
        path=data_dir / "settings.json",
        default_commission=config.default_commission_percent,
        env_links=config.links,
    )
    settings.set_commission(config.default_commission_percent)
    for key, value in config.links.items():
        settings.set_link(key, value)
    users = UsersStore(path=data_dir / "users.json")
    rates = RateService(coins=COINS, fallback_rates=FALLBACK_RATES, ttl_seconds=60)
    ctx = AppContext(
        settings=settings,
        users=users,
        rates=rates,
        admin_ids=config.admin_ids,
        env_path=base_dir / ".env",
    )

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    me = await bot.get_me()
    if me.username:
        ctx.bot_username = me.username

    dp = Dispatcher()
    dp.include_router(build_buy_router(ctx, assets_dir))
    dp.include_router(build_sell_router(ctx, assets_dir))
    dp.include_router(build_admin_router(ctx))
    dp.include_router(build_common_router(ctx, assets_dir))

    print(f"Bot started: @{ctx.bot_username}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run())
