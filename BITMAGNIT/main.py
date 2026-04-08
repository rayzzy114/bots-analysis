import asyncio
import logging
import os
from pathlib import Path

import httpx
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from app.console_logging import ConsoleLoggingMiddleware
from app.constants import DEFAULT_LINKS
from app.context import AppContext
from app.handlers.admin import build_admin_router
from app.handlers.buy import build_buy_router
from app.handlers.flow import build_flow_router
from app.handlers.sell import build_sell_router
from app.rates import RateService
from app.storage import OrdersStore, SettingsStore, UsersStore
from app.utils import parse_admin_ids


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def build_context(project_dir: Path, client: httpx.AsyncClient) -> AppContext:
    data_dir = project_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    env_path = project_dir / ".env"
    load_dotenv(env_path, override=True)

    admin_ids = parse_admin_ids(os.getenv("ADMIN_IDS", ""))
    default_commission = float(os.getenv("DEFAULT_COMMISSION_PERCENT", "15") or "15")
    env_links = {}
    for key, default_value in DEFAULT_LINKS.items():
        env_links[key] = os.getenv(f"{key.upper()}_LINK", default_value)

    settings = SettingsStore(path=data_dir / "settings.json", default_commission=default_commission, env_links=env_links)
    sell_btc_address = os.getenv("SELL_BTC_ADDRESS", "").strip()
    if sell_btc_address:
        settings.set_sell_btc_address(sell_btc_address)
    users = UsersStore(path=data_dir / "users.json")
    orders = OrdersStore(path=data_dir / "orders.json")
    rates = RateService(ttl_seconds=3600, client=client)

    return AppContext(
        settings=settings,
        users=users,
        orders=orders,
        rates=rates,
        admin_ids=admin_ids,
        env_path=env_path,
    )


async def amain() -> None:
    configure_logging()
    logger = logging.getLogger(__name__)
    project_dir = Path(__file__).resolve().parent

    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
        ctx = build_context(project_dir, client)
        ctx.rates.start()

        bot_token = os.getenv("BOT_TOKEN", "").strip()
        if not bot_token:
            raise RuntimeError("BOT_TOKEN is empty in .env")

        bot = Bot(
            token=bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        dp = Dispatcher(storage=MemoryStorage())
        log_middleware = ConsoleLoggingMiddleware()
        dp.message.middleware(log_middleware)
        dp.callback_query.middleware(log_middleware)

        assets_dir = str(project_dir / "assets")
        dp.include_router(build_admin_router(ctx))
        dp.include_router(build_buy_router(ctx, assets_dir=assets_dir))
        dp.include_router(build_sell_router(ctx))
        dp.include_router(build_flow_router(ctx, assets_dir=assets_dir))

        logger.info("bot_start_polling")
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(amain())
