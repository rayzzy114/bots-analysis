import asyncio
import os
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from app.constants import DEFAULT_LINKS
from app.context import AppContext
from app.handlers.admin import build_admin_router
from app.handlers.flow import build_flow_router, schedule_pending_requisites_recovery
from app.rates import RateService
from app.storage import OrdersStore, SettingsStore, UsersStore
from app.utils import parse_admin_ids


def parse_default_commission(raw_value: str | None) -> float:
    try:
        value = float((raw_value or "").strip() or "15")
    except (TypeError, ValueError):
        return 15.0
    if 0 <= value <= 50:
        return value
    return 15.0


def build_context(project_dir: Path) -> AppContext:
    data_dir = project_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    env_path = project_dir / ".env"
    load_dotenv(env_path, override=True)

    admin_ids = parse_admin_ids(os.getenv("ADMIN_IDS", ""))
    default_commission = parse_default_commission(os.getenv("DEFAULT_COMMISSION_PERCENT"))
    env_links: dict[str, str] = {}
    for key, default_value in DEFAULT_LINKS.items():
        env_links[key] = os.getenv(f"{key.upper()}_LINK", default_value)

    settings = SettingsStore(path=data_dir / "settings.json", default_commission=default_commission, env_links=env_links)
    users = UsersStore(path=data_dir / "users.json")
    orders = OrdersStore(path=data_dir / "orders.json")
    rates = RateService(ttl_seconds=45)

    return AppContext(
        settings=settings,
        users=users,
        orders=orders,
        rates=rates,
        admin_ids=admin_ids,
        env_path=env_path,
    )


async def amain() -> None:
    project_dir = Path(__file__).resolve().parent
    ctx = build_context(project_dir)

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is empty in .env")

    bot = Bot(
        token=bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    me = await bot.get_me()
    supports_inline_queries = bool(getattr(me, "supports_inline_queries", False))
    dp = Dispatcher(storage=MemoryStorage())
    flow_file = str(project_dir / "captured_flow.json")

    dp.include_router(build_admin_router(ctx))
    flow_router = build_flow_router(
        ctx=ctx,
        assets_dir=str(project_dir / "assets"),
        flow_file=flow_file,
        supports_inline_queries=supports_inline_queries,
    )
    dp.include_router(flow_router)
    schedule_pending_requisites_recovery(
        ctx=ctx,
        bot=bot,
        flow_file=flow_file,
        supports_inline_queries=supports_inline_queries,
    )

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(amain())
