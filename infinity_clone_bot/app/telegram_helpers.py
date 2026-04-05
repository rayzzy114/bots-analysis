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
