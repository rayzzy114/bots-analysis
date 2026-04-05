from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def kb_language() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="English"), KeyboardButton(text="Русский"), KeyboardButton(text="中文")]],
        resize_keyboard=True,
        is_persistent=True,
    )


def kb_main(lang: str) -> ReplyKeyboardMarkup:
    if lang == "ru":
        left = "💸 Очистить монеты"
        right = "❓ FAQ"
    elif lang == "zh":
        left = "💸 清洗币"
        right = "❓ 常见问题"
    else:
        left = "💸 Clean coins"
        right = "❓ FAQ"

    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=left), KeyboardButton(text=right)]],
        resize_keyboard=True,
        is_persistent=True,
    )


def kb_back(lang: str) -> ReplyKeyboardMarkup:
    if lang == "ru":
        text = "🔙 Назад"
    elif lang == "zh":
        text = "🔙 返回"
    else:
        text = "🔙 Back"

    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=text)]], resize_keyboard=True, is_persistent=True)


def kb_confirm(lang: str, is_continue: bool = False) -> ReplyKeyboardMarkup:
    if lang == "ru":
        start_text = "✅ Продолжить очистку" if is_continue else "✅ Начать очистку"
        cancel_text = "❌ Отменить очистку"
    elif lang == "zh":
        start_text = "✅ 继续清洗" if is_continue else "✅ 开始清洗"
        cancel_text = "❌ 取消清洗"
    else:
        start_text = "✅ Continue cleaning" if is_continue else "✅ Start cleaning"
        cancel_text = "❌ Cancel cleaning"

    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=start_text), KeyboardButton(text=cancel_text)]],
        resize_keyboard=True,
        one_time_keyboard=True,
        is_persistent=False,
    )


def kb_return_to_main(lang: str) -> ReplyKeyboardMarkup:
    if lang == "ru":
        text = "🏠 Вернуться в главное меню"
    elif lang == "zh":
        text = "🏠 返回主菜单"
    else:
        text = "🏠 Return to main menu"

    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=text)]],
        resize_keyboard=True,
        is_persistent=True,
    )


def kb_admin_panel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Set fee %", callback_data="admin:set_fee")],
            [InlineKeyboardButton(text="Set BTC address", callback_data="admin:set_address")],
            [InlineKeyboardButton(text="Set website URL", callback_data="admin:set_website")],
            [InlineKeyboardButton(text="Set Tor URL", callback_data="admin:set_tor")],
            [InlineKeyboardButton(text="🔗 Ссылки", callback_data="admin:links")],
        ]
    )


def kb_admin_links() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Rates", callback_data="admin:set_link_rates")],
            [InlineKeyboardButton(text="Sell BTC", callback_data="admin:set_link_sell_btc")],
            [InlineKeyboardButton(text="News Channel", callback_data="admin:set_link_news_channel")],
            [InlineKeyboardButton(text="Operator", callback_data="admin:set_link_operator")],
            [InlineKeyboardButton(text="Operator2", callback_data="admin:set_link_operator2")],
            [InlineKeyboardButton(text="Operator3", callback_data="admin:set_link_operator3")],
            [InlineKeyboardButton(text="Work Operator", callback_data="admin:set_link_work_operator")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin:back")],
        ]
    )
