"""Точка входа клона @NeskafeEx_bot."""

from __future__ import annotations

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from app.handlers import account, admin, common, exchange, start
from app.runtime import AppContext


def _load_dotenv(path: str | None = None) -> None:
    """Подхватить переменные из .env (KEY=VALUE), без сторонних зависимостей.

    Файл ищем рядом с main.py. Уже заданные переменные не перезаписываем.
    """
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


async def _inject_ctx(handler, event, data):
    """Middleware: прокидывает AppContext во все хендлеры как ctx."""
    data["ctx"] = data["dispatcher"]["ctx"]
    return await handler(event, data)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    _load_dotenv()  # загрузить .env рядом с main.py (если есть)
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

    # Меню команд (popup при вводе «/»)
    await bot.set_my_commands([
        BotCommand(command="restart", description="🔄 если что-то пошло не так"),
    ])

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
