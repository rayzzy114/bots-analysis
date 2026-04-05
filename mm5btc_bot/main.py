from __future__ import annotations

import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

from app.context import AppContext
from app.handlers import build_admin_router, build_user_router
from app.storage import RuntimeStore, SettingsStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")


def _parse_admin_ids(raw: str) -> set[int]:
    result: set[int] = set()
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            result.add(int(part))
        except ValueError:
            continue
    return result


async def run() -> None:
    root_dir = Path(__file__).resolve().parent
    load_dotenv(root_dir / ".env", encoding="utf-8-sig")

    token = (os.getenv("BOT_TOKEN") or os.getenv("\ufeffBOT_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is required in .env")

    settings = SettingsStore(root_dir / "data" / "settings.json")
    runtime = RuntimeStore(root_dir / "data" / "runtime.json")
    admin_ids = _parse_admin_ids(os.getenv("ADMIN_IDS", os.getenv("\ufeffADMIN_IDS", "")))

    ctx = AppContext(root_dir=root_dir, settings=settings, runtime=runtime, admin_ids=admin_ids)

    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    me = await bot.get_me()
    current = settings.get()
    print(
        "[STARTED] "
        f"@{me.username or 'unknown'} "
        f"(id={me.id}) admins={len(admin_ids)} "
        f"deposit={current.get('deposit_btc_address')}"
    )
    dp = Dispatcher()

    dp.include_router(build_admin_router(ctx))
    dp.include_router(build_user_router(ctx))

    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio

    asyncio.run(run())
