from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from .constants import LINK_LABELS


def kb_main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📈 Купить"), KeyboardButton(text="📉 Продать")],
            [KeyboardButton(text="🧮 Калькулятор")],
            [KeyboardButton(text="💻 Личный кабинет"), KeyboardButton(text="📱 Контакты")],
        ],
        resize_keyboard=True,
    )


def kb_buy_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔄 Купить BTC"), KeyboardButton(text="🔄 Купить LTC")],
            [KeyboardButton(text="🔄 Купить XMR"), KeyboardButton(text="🔄 Купить USDT-TRC20")],
            [KeyboardButton(text="⬅️ Назад")],
        ],
        resize_keyboard=True,
    )


def kb_calc_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="BTC"), KeyboardButton(text="LTC")],
            [KeyboardButton(text="XMR"), KeyboardButton(text="USDT")],
            [KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True,
    )


def kb_cancel() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def kb_cabinet_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔐 Кошелек"), KeyboardButton(text="🏷 Промокод")],
            [KeyboardButton(text="Вывести реф. счет"), KeyboardButton(text="🎰 Испытай удачу")],
            [KeyboardButton(text="📚 Мои адреса")],
            [KeyboardButton(text="⬅️ Назад")],
        ],
        resize_keyboard=True,
    )


def kb_wallet_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⬇️ Депозит"), KeyboardButton(text="⬆️ Вывод")],
            [KeyboardButton(text="⬅️ Назад")],
        ],
        resize_keyboard=True,
    )


def kb_wallet_coin_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="BTC"), KeyboardButton(text="LTC")],
            [KeyboardButton(text="XMR"), KeyboardButton(text="USDT")],
            [KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True,
    )


def kb_addresses_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Добавить адрес")],
            [KeyboardButton(text="🗓️ Посмотреть мои адреса")],
            [KeyboardButton(text="⬅️ Назад")],
        ],
        resize_keyboard=True,
    )


def kb_buy_payment_methods(methods: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=title, callback_data=f"buy:method:{index}")]
        for index, title in enumerate(methods)
    ]
    rows.append([InlineKeyboardButton(text="❌ Отменить заявку", callback_data="buy:flow:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_buy_order_actions(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"buy:paid:{order_id}")],
            [InlineKeyboardButton(text="❌ Отменить заявку", callback_data=f"buy:cancel:{order_id}")],
        ]
    )


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


def kb_contacts(links: dict[str, str]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📡 Канал", url=links.get("channel", "#")),
                InlineKeyboardButton(text="🗨️ Чат", url=links.get("chat", "#")),
            ],
            [
                InlineKeyboardButton(text="🌟 Отзывы", url=links.get("reviews", "#")),
                InlineKeyboardButton(text="✍️ Оставить отзыв", url=links.get("review_form", "#")),
            ],
            [
                InlineKeyboardButton(text="🧑‍🚀 Менеджер", url=links.get("manager", "#")),
                InlineKeyboardButton(text="👽 Оператор", url=links.get("operator", "#")),
            ],
            [InlineKeyboardButton(text="📜 Условия", url=links.get("terms", "#"))],
            [InlineKeyboardButton(text="FAQ", url=links.get("faq", "#"))],
        ]
    )


def kb_admin_panel(commission_percent: float) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"Комиссия: {commission_percent:.2f}%", callback_data="admin:set_commission")],
            [InlineKeyboardButton(text="💳 Управление реквизитами", callback_data="admin:requisites")],
            [InlineKeyboardButton(text="⚙️ ENV KEY=VALUE", callback_data="admin:set_env")],
            [
                InlineKeyboardButton(text="FAQ", callback_data="admin:set_link:faq"),
                InlineKeyboardButton(text="Канал", callback_data="admin:set_link:channel"),
            ],
            [
                InlineKeyboardButton(text="Чат", callback_data="admin:set_link:chat"),
                InlineKeyboardButton(text="Отзывы", callback_data="admin:set_link:reviews"),
            ],
            [
                InlineKeyboardButton(text="Отзыв-форма", callback_data="admin:set_link:review_form"),
                InlineKeyboardButton(text="Менеджер", callback_data="admin:set_link:manager"),
            ],
            [
                InlineKeyboardButton(text="Оператор", callback_data="admin:set_link:operator"),
                InlineKeyboardButton(text="Условия", callback_data="admin:set_link:terms"),
            ],
            [InlineKeyboardButton(text="🔄 Обновить курсы", callback_data="admin:rates")],
        ]
    )


def kb_admin_requisites(commission_percent: float, mode_label: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"🔃 Режим: {mode_label}", callback_data="admin:req:toggle_mode")],
            [
                InlineKeyboardButton(text="🏦 Банк", callback_data="admin:req:edit_bank"),
                InlineKeyboardButton(text="✏️ Реквизиты", callback_data="admin:req:edit_value"),
            ],
            [
                InlineKeyboardButton(
                    text=f"💵 Комиссия: {commission_percent:.2f}%",
                    callback_data="admin:req:commission",
                )
            ],
            [
                InlineKeyboardButton(text="➕ Способ оплаты", callback_data="admin:req:add_method"),
                InlineKeyboardButton(text="➖ Удалить способ", callback_data="admin:req:delete_method_menu"),
            ],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="admin:req:back")],
        ]
    )


def kb_admin_delete_payment_method(methods: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"❌ {title}", callback_data=f"admin:req:del_method:{index}")]
        for index, title in enumerate(methods)
    ]
    rows.append([InlineKeyboardButton(text="↩️ Назад", callback_data="admin:requisites")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_admin_split_methods_pick(methods: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=title, callback_data=f"admin:req:edit_method:{index}")]
        for index, title in enumerate(methods)
    ]
    rows.append([InlineKeyboardButton(text="↩️ Назад", callback_data="admin:requisites")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def links_help_lines(links: dict[str, str]) -> str:
    lines = []
    for key, label in LINK_LABELS.items():
        lines.append(f"{label}: {links.get(key, '-')}")
    return "\n".join(lines)


def kb_saved_addresses(addresses: list[dict[str, str]]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"{item['name']} ({item['coin']})", callback_data=f"addr:view:{index}")]
        for index, item in enumerate(addresses)
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_saved_address_actions(index: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Удалить", callback_data=f"addr:delete:{index}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="addr:back:list")],
        ]
    )
