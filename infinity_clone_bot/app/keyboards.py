from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .storage import SettingsStore


def kb_main(settings: SettingsStore) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💳 Купить", callback_data="menu:buy"),
                InlineKeyboardButton(text="🏧 Продать", callback_data="menu:sell"),
            ],
            [InlineKeyboardButton(text="🛸 Командный модуль", callback_data="menu:module")],
            [
                InlineKeyboardButton(text="🔍 FAQ", url=settings.link("faq")),
                InlineKeyboardButton(text="✉️ Контакты", callback_data="menu:contacts"),
            ],
        ]
    )


def kb_back_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="nav:main")]]
    )


def kb_back_module() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="menu:module")]]
    )


def kb_buy_coins() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Bitcoin (BTC)", callback_data="buy:coin:btc"),
                InlineKeyboardButton(text="Litecoin (LTC)", callback_data="buy:coin:ltc"),
            ],
            [InlineKeyboardButton(text="Tether (USDT)", callback_data="buy:coin:usdt")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="nav:main")],
        ]
    )


def kb_buy_method(settings: SettingsStore) -> InlineKeyboardMarkup:
    method_rows = [
        [InlineKeyboardButton(text=title, callback_data=f"buy:method:{index}")]
        for index, title in enumerate(settings.payment_methods())
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            *method_rows,
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:buy")],
        ]
    )


def kb_buy_confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="ИСП. БАЛАНС КОШЕЛЬКА", callback_data="buy:wallet_balance")],
            [
                InlineKeyboardButton(text="✅ Согласен", callback_data="buy:confirm"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="nav:main"),
            ],
        ]
    )


def kb_buy_order_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Я ОПЛАТИЛ", callback_data="buy:paid")],
            [InlineKeyboardButton(text="ОТМЕНИТЬ ЗАЯВКУ", callback_data="nav:main")],
        ]
    )


def kb_sell_coins() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Bitcoin (BTC)", callback_data="sell:coin:btc"),
                InlineKeyboardButton(text="Litecoin (LTC)", callback_data="sell:coin:ltc"),
            ],
            [InlineKeyboardButton(text="Tether (USDT)", callback_data="sell:coin:usdt")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="nav:main")],
        ]
    )


def kb_sell_confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Продать", callback_data="sell:confirm")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="nav:main")],
        ]
    )


def kb_contacts(settings: SettingsStore) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📡 Канал", url=settings.link("channel")),
                InlineKeyboardButton(text="🗨️ Чат", url=settings.link("chat")),
            ],
            [
                InlineKeyboardButton(text="🌟 Отзывы", url=settings.link("reviews")),
                InlineKeyboardButton(text="✍️ Оставить отзыв", callback_data="contacts:review"),
            ],
            [
                InlineKeyboardButton(text="🧑‍🚀 Менеджер", url=settings.link("manager")),
                InlineKeyboardButton(text="👽 Оператор", url=settings.link("operator")),
            ],
            [InlineKeyboardButton(text="📜 Условия|ПС", url=settings.link("terms"))],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="nav:main")],
        ]
    )


def kb_sell_operator() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Оператор", url="https://t.me/operator_infinity")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="nav:main")],
        ]
    )


def kb_module() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎫 Промокод", callback_data="module:promo"),
                InlineKeyboardButton(text="🤝 Партнёрка", callback_data="module:partner"),
            ],
            [
                InlineKeyboardButton(text="💸 Кешбэк", callback_data="module:cashback"),
                InlineKeyboardButton(text="🚀 Вывести бонусы", callback_data="module:withdraw"),
            ],
            [InlineKeyboardButton(text="📜 История обменов", callback_data="module:history")],
            [InlineKeyboardButton(text="↩️ Назад", callback_data="nav:main")],
        ]
    )


def kb_cancel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="nav:main")]]
    )


def kb_admin_panel(commission_percent: float) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"Комиссия: {commission_percent:.2f}%", callback_data="admin:set_commission")],
            [InlineKeyboardButton(text="🧾 Управление реквизитами", callback_data="admin:requisites")],
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
                InlineKeyboardButton(text="Оставить отзыв", callback_data="admin:set_link:review_form"),
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
            [InlineKeyboardButton(text=f"🔄 Режим: {mode_label}", callback_data="admin:req:toggle_mode")],
            [
                InlineKeyboardButton(text="✏️ Реки", callback_data="admin:req:edit_value"),
                InlineKeyboardButton(text="✏️ Банк", callback_data="admin:req:edit_bank"),
            ],
            [InlineKeyboardButton(text=f"💵 Комиссия: {commission_percent:.2f}%", callback_data="admin:req:commission")],
            [
                InlineKeyboardButton(text="➕ Способ оплаты", callback_data="admin:req:add_method"),
                InlineKeyboardButton(text="➖ Удалить способ", callback_data="admin:req:delete_method_menu"),
            ],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="admin:req:back")],
        ]
    )


def kb_admin_delete_payment_method(methods: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"❌ {title}", callback_data=f"admin:req:del:{index}")]
        for index, title in enumerate(methods)
    ]
    rows.append([InlineKeyboardButton(text="↩️ Назад к реквизитам", callback_data="admin:requisites")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_captcha_fruits() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🍏", callback_data="captcha:apple"),
                InlineKeyboardButton(text="🍇", callback_data="captcha:grapes"),
                InlineKeyboardButton(text="🍒", callback_data="captcha:cherries"),
            ],
            [
                InlineKeyboardButton(text="🫐", callback_data="captcha:blueberries"),
                InlineKeyboardButton(text="🍑", callback_data="captcha:peach"),
                InlineKeyboardButton(text="🍐", callback_data="captcha:pear"),
            ],
        ]
    )


def kb_buy_payment_methods() -> InlineKeyboardMarkup:
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="СБП", callback_data="pay_sbp")],
        [InlineKeyboardButton(text="Карта", callback_data="pay_card")],
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")],
    ])


def kb_main_menu() -> InlineKeyboardMarkup:
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Купить", callback_data="buy")],
        [InlineKeyboardButton(text="Продать", callback_data="sell")],
    ])
