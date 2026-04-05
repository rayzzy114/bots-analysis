from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def kb_welcome() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇹🇷 Турция", callback_data="menu:turkey"),
            InlineKeyboardButton(text="🇹🇭 Таиланд", callback_data="menu:rates_th"),
        ],
        [
            InlineKeyboardButton(text="🇨🇳 Китай", callback_data="menu:china"),
            InlineKeyboardButton(text="🇦🇪 Дубай", callback_data="menu:dubai"),
        ],
        [
            InlineKeyboardButton(text="🇮🇩 Бали", callback_data="menu:bali"),
            InlineKeyboardButton(text="🌐 Рус / Eng", callback_data="menu:lang"),
        ],
    ])


def kb_source_choice() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌐 Онлайн", callback_data="source:online"),
        ],
        [
            InlineKeyboardButton(text="🏠 Офлайн", callback_data="source:offline"),
        ],
    ])


def kb_country_sub(country: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Наши курсы",
                callback_data=f"menu:{country}_rates",
            ),
            InlineKeyboardButton(
                text="Способы получения",
                callback_data=f"menu:{country}_methods",
            ),
        ],
    ])


def kb_rating(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="☹️ 1", callback_data=f"rate:{user_id}:1"),
            InlineKeyboardButton(text="🫤 2", callback_data=f"rate:{user_id}:2"),
            InlineKeyboardButton(text="😐 3", callback_data=f"rate:{user_id}:3"),
            InlineKeyboardButton(text="🙂 4", callback_data=f"rate:{user_id}:4"),
            InlineKeyboardButton(text="🤩 5", callback_data=f"rate:{user_id}:5"),
        ],
    ])


def kb_close_select(users: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    """users: list of (user_id, description)"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=desc, callback_data=f"admin:close:{uid}")]
        for uid, desc in users
    ])


def kb_review(review_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐ Оставить отзыв", url=review_url),
        ],
    ])


def kb_admin_reply(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="💬 Ответить",
                callback_data=f"admin:reply_to:{user_id}",
            ),
            InlineKeyboardButton(
                text="🚫 Забанить",
                callback_data=f"admin:ban:{user_id}",
            ),
        ],
    ])


def kb_unban(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Разбанить",
                callback_data=f"admin:unban:{user_id}",
            ),
        ],
    ])
