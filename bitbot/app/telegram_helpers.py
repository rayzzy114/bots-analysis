import asyncio

from aiogram.exceptions import TelegramNetworkError
from aiogram.types import CallbackQuery, Message


async def answer_with_retry(
    message: Message,
    text: str,
    reply_markup=None,
    retries: int = 3,
    retry_backoff_seconds: float = 1.0,
) -> bool:
    for attempt in range(max(1, retries)):
        try:
            await message.answer(text, reply_markup=reply_markup)
            return True
        except TelegramNetworkError:
            if attempt + 1 >= retries:
                break
            await asyncio.sleep(max(0.1, retry_backoff_seconds) * (attempt + 1))
    return False


def callback_message(callback: CallbackQuery) -> Message | None:
    if isinstance(callback.message, Message):
        return callback.message
    return None


def callback_user_id(callback: CallbackQuery) -> int | None:
    if callback.from_user is None:
        return None
    return callback.from_user.id


def message_user_id(message: Message) -> int | None:
    if message.from_user is None:
        return None
    return message.from_user.id
