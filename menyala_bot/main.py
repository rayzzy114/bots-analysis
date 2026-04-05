import asyncio
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from app.config import load_config
from app.context import AppContext
from app.handlers.admin import build_admin_router
from app.handlers.buy import build_buy_router
from app.handlers.common import build_common_router
from app.rates import RateService
from app.storage import OrdersStore, SettingsStore, UsersStore


async def set_default_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Запустить бота"),
            BotCommand(command="rates", description="Показать курсы"),
            BotCommand(command="admin", description="Админ-панель"),
        ]
    )


async def main() -> None:
    base_dir = Path(__file__).resolve().parent
    config = load_config(base_dir)

    settings = SettingsStore(
        path=base_dir / "data" / "settings.json",
        default_commission=config.default_commission_percent,
        env_links=config.links,
    )
    users = UsersStore(path=base_dir / "data" / "users.json")
    orders = OrdersStore(path=base_dir / "data" / "orders.json")
    rates = RateService()

    ctx = AppContext(
        settings=settings,
        users=users,
        orders=orders,
        rates=rates,
        admin_ids=set(config.admin_ids),
        env_path=config.env_path,
    )

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(build_admin_router(ctx))
    dp.include_router(build_buy_router(ctx))
    dp.include_router(build_common_router(ctx))

    await set_default_commands(bot)

    for admin_id in ctx.admin_ids:
        try:
            await bot.send_message(admin_id, "Бот запущен.")
        except Exception:
            pass

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
