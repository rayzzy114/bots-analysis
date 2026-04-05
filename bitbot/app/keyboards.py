from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from .constants import BUY_BUTTON_TO_COIN, LINK_LABELS, SELL_BUTTON_TO_COIN


def kb_main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💸 Мой кошелек")],
            [KeyboardButton(text="📈 Купить"), KeyboardButton(text="📉 Продать")],
            [KeyboardButton(text="🧮 Калькулятор")],
            [KeyboardButton(text="💻 Личный кабинет"), KeyboardButton(text="📱 Контакты")],
        ],
        resize_keyboard=True,
    )


def kb_antispam_fire() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✈️")],
            [KeyboardButton(text="🚀")],
            [KeyboardButton(text="🌙")],
            [KeyboardButton(text="🔥")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def kb_wallet_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 История транзакций"), KeyboardButton(text="💰 Баланс")],
            [KeyboardButton(text="📩 Получить адреса"), KeyboardButton(text="🔄 Отправить валюту")],
            [KeyboardButton(text="⬅️ Назад")],
        ],
        resize_keyboard=True,
    )


def kb_wallet_history_status() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="ОТПРАВЛЕНО"), KeyboardButton(text="ПОЛУЧЕНО")],
            [KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True,
    )


def kb_buy_menu() -> ReplyKeyboardMarkup:
    buttons = list(BUY_BUTTON_TO_COIN.keys())
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=buttons[0]), KeyboardButton(text=buttons[1])],
            [KeyboardButton(text=buttons[2]), KeyboardButton(text=buttons[3])],
            [KeyboardButton(text=buttons[4]), KeyboardButton(text=buttons[5])],
            [KeyboardButton(text="⬅️ Назад")],
        ],
        resize_keyboard=True,
    )


def kb_sell_menu() -> ReplyKeyboardMarkup:
    buttons = list(SELL_BUTTON_TO_COIN.keys())
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=buttons[0]), KeyboardButton(text=buttons[1])],
            [KeyboardButton(text=buttons[2]), KeyboardButton(text=buttons[3])],
            [KeyboardButton(text=buttons[4]), KeyboardButton(text=buttons[5])],
            [KeyboardButton(text="⬅️ Назад")],
        ],
        resize_keyboard=True,
    )


def kb_calc_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="BTC"), KeyboardButton(text="LTC"), KeyboardButton(text="XMR")],
            [KeyboardButton(text="USDT"), KeyboardButton(text="TRX"), KeyboardButton(text="ETH")],
            [KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True,
    )


def kb_cabinet_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Вывести кешбек"), KeyboardButton(text="Вывести реф. счет")],
            [KeyboardButton(text="🏷 Промокод"), KeyboardButton(text="🎰 Испытай удачу")],
            [KeyboardButton(text="⬅️ Назад")],
        ],
        resize_keyboard=True,
    )


def kb_cancel() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def kb_sell_requisites_method() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Номер карты")],
            [KeyboardButton(text="Номер телефона")],
            [KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True,
    )


def kb_buy_payment_methods(methods: list[str]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=item, callback_data=f"buy:method:{idx}")] for idx, item in enumerate(methods)]
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="buy:flow:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_buy_order_actions(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"buy:paid:{order_id}")],
            [InlineKeyboardButton(text="❌ Отменить заявку", callback_data=f"buy:cancel:{order_id}")],
        ]
    )


def kb_buy_next_step() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Далее ➡️", callback_data="buy:next")]]
    )


def kb_buy_donation_step() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚪ Да", callback_data="buy:donation:yes"),
                InlineKeyboardButton(text="🟢 Нет", callback_data="buy:donation:no"),
            ],
            [InlineKeyboardButton(text="Далее ➡️", callback_data="buy:next:wallet")],
        ]
    )


def kb_buy_wallet_choice() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена"), KeyboardButton(text="💸 На мой кошелек")]],
        resize_keyboard=True,
    )


def kb_sell_order_actions(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Продолжить", callback_data=f"sell:continue:{order_id}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"sell:cancel:{order_id}")],
        ]
    )


def kb_admin_order_confirm(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить выдачу", callback_data=f"admin:order:confirm:{order_id}")]
        ]
    )


def kb_contacts(links: dict[str, str]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Беседка", url=links.get("chat", "#"))],
            [InlineKeyboardButton(text="Отзывы", url=links.get("reviews", "#"))],
            [InlineKeyboardButton(text="BOSS", url=links.get("manager", "#"))],
            [InlineKeyboardButton(text="SUPPORT", url=links.get("operator", "#"))],
            [InlineKeyboardButton(text="PR менеджер", url=links.get("manager", "#"))],
            [InlineKeyboardButton(text="Новости", url=links.get("channel", "#"))],
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
            [InlineKeyboardButton(text="₿ BTC адрес (sell)", callback_data="admin:req:edit_sell_btc")],
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
    rows = [[InlineKeyboardButton(text=f"❌ {item}", callback_data=f"admin:req:del_method:{idx}")] for idx, item in enumerate(methods)]
    rows.append([InlineKeyboardButton(text="↩️ Назад", callback_data="admin:requisites")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_admin_split_methods_pick(methods: list[str]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=item, callback_data=f"admin:req:edit_method:{idx}")] for idx, item in enumerate(methods)]
    rows.append([InlineKeyboardButton(text="↩️ Назад", callback_data="admin:requisites")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def links_help_lines(links: dict[str, str]) -> str:
    lines = []
    for key, label in LINK_LABELS.items():
        lines.append(f"{label}: {links.get(key, '-')}")
    return "\n".join(lines)
