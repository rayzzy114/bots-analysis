from __future__ import annotations

import datetime

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def kb_history_page(
    orders: list[dict],
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    """Inline keyboard for paginated order history."""
    rows: list[list[InlineKeyboardButton]] = []
    for order in orders:
        ts = order.get("created_at", 0)
        dt = datetime.datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M")
        order_id = order.get("order_id", "?")
        rows.append([
            InlineKeyboardButton(
                text=f"#{order_id} ({dt})",
                callback_data=f"history:order:{order_id}",
            )
        ])
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            text="⬅ Назад",
            callback_data=f"history:page:{page - 1}",
        ))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(
            text="Вперед ➡",
            callback_data=f"history:page:{page + 1}",
        ))
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)
