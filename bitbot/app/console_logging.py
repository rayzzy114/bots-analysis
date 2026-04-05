import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject


logger = logging.getLogger("bot.console")


def _trim_text(value: str, max_len: int = 160) -> str:
    text = value.replace("\n", "\\n").strip()
    if len(text) <= max_len:
        return text
    return f"{text[:max_len]}..."


class ConsoleLoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            if isinstance(event, Message):
                user_id = event.from_user.id if event.from_user is not None else None
                username = event.from_user.username if event.from_user is not None else None
                text = event.text or event.caption or ""
                logger.info(
                    "message user_id=%s username=%s text=%s",
                    user_id,
                    username or "-",
                    _trim_text(text),
                )
            elif isinstance(event, CallbackQuery):
                user_id = event.from_user.id if event.from_user is not None else None
                username = event.from_user.username if event.from_user is not None else None
                logger.info(
                    "callback user_id=%s username=%s data=%s",
                    user_id,
                    username or "-",
                    _trim_text(event.data or ""),
                )

            return await handler(event, data)
        except Exception:
            logger.exception("handler_failed event=%s", type(event).__name__)
            raise
