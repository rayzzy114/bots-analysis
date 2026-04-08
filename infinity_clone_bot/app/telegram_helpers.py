from aiogram.types import CallbackQuery, Message


def callback_message(callback: CallbackQuery) -> Message | None:
    message = callback.message
    if isinstance(message, Message):
        return message
    return None


def message_user_id(message: Message) -> int | None:
    user = message.from_user
    if user is None:
        return None
    return user.id


def callback_user_id(callback: CallbackQuery) -> int | None:
    user = callback.from_user
    if user is None:
        return None
    return user.id


async def answer_with_retry(callback, text: str, show_alert: bool = False, retries: int = 3) -> None:
    """Answer callback query with retry logic."""
    for attempt in range(retries):
        try:
            await callback.answer(text, show_alert=show_alert)
            return
        except Exception:
            if attempt < retries - 1:
                import asyncio
                await asyncio.sleep(0.5)
            else:
                raise
