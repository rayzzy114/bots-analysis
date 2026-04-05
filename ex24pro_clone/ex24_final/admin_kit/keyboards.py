from __future__ import annotations

from html import escape

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .config import LinkDefinition


def kb_admin_order_confirm(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить выдачу",
                    callback_data=f"admin:order:confirm:{order_id}",
                )
            ]
        ]
    )


def kb_admin_panel(
    commission_percent: float,
    link_definitions: tuple[LinkDefinition, ...],
    *,
    has_sell_wallets: bool,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=f"Спред: {commission_percent:.2f}%", callback_data="admin:set_commission")],
        [InlineKeyboardButton(text="⚙️ ENV KEY=VALUE", callback_data="admin:set_env")],
    ]
    pair: list[InlineKeyboardButton] = []
    for item in link_definitions:
        pair.append(InlineKeyboardButton(text=item.label, callback_data=f"admin:set_link:{item.key}"))
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.append([InlineKeyboardButton(text="📢 Рассылка всем", callback_data="admin:broadcast")])
    rows.append([InlineKeyboardButton(text="🔄 Обновить курсы", callback_data="admin:rates")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def links_help_lines(link_definitions: tuple[LinkDefinition, ...], links: dict[str, str]) -> str:
    lines = []
    for item in link_definitions:
        value = links.get(item.key, "-") or "-"
        lines.append(f"{item.label}: {escape(value, quote=False)}")
    return "\n".join(lines)
