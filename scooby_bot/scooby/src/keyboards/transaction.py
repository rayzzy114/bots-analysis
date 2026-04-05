from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def buy_button():
    buttons = [
        [InlineKeyboardButton(text="BTC", callback_data="buy_btc")],
        [InlineKeyboardButton(text="XMR", callback_data="buy_xmr")],
        [InlineKeyboardButton(text="LTC", callback_data="buy_ltc")],
        [InlineKeyboardButton(text="🎟 Активировать купон", callback_data="busy")],
        [InlineKeyboardButton(text="📜 Главное меню", callback_data="home")],
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def buy_button_operation(crypto=False, currency="btc"):
    buttons = [
        [InlineKeyboardButton(text="Калькулятор", callback_data=f"calc_from_buy_{currency}"),
         InlineKeyboardButton(
             text="В крипте" if crypto else "В рублях",
             callback_data="operation_buy_crypto" if crypto else "operation_buy_ru"
         )],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="buy"),
         InlineKeyboardButton(text="📜 Главное меню", callback_data="home")],

    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def sale_button_operation(crypto=False, currency="btc"):
    buttons = [
        [InlineKeyboardButton(text="Калькулятор", callback_data=f"calc_from_sale_{currency}"),
         InlineKeyboardButton(
             text="В крипте" if crypto else "В рублях",
             callback_data="operation_sale_crypto" if crypto else "operation_sale_ru"
         )],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="sale"),
         InlineKeyboardButton(text="📜 Главное меню", callback_data="home")],

    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def sale_button():
    buttons = [
        [InlineKeyboardButton(text="BTC", callback_data="sale_btc")],
        [InlineKeyboardButton(text="XMR", callback_data="sale_xmr")],
        [InlineKeyboardButton(text="LTC", callback_data="sale_ltc")],
        [InlineKeyboardButton(text="USDT", callback_data="sale_usdt")],
        [InlineKeyboardButton(text="📜 Главное меню", callback_data="home")],
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def button_buy_back():
    buttons = [
        [InlineKeyboardButton(text="🔙 Назад", callback_data="buy")],
        [InlineKeyboardButton(text="📜 Главное меню", callback_data="home")],
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def success_sale_button():
    buttons = [
        [InlineKeyboardButton(text="✅ Создать заявку", callback_data="success_sale")],
        [InlineKeyboardButton(text="📜 Главное меню", callback_data="home")],
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def payment_count_button():
    buttons = [
        [InlineKeyboardButton(text="1️⃣ : 1 платёж, время выплаты до 12 часов", callback_data="payment_count_1")],
        [InlineKeyboardButton(text="2️⃣ : 2-4 платёж, время выплаты до 6 часов", callback_data="payment_count_2")],
        [InlineKeyboardButton(text="3️⃣ : 4+ платежей, время выплаты до 2 часов", callback_data="payment_count_3")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def success_sale_button_final():
    buttons = [
        [InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data="success_sale_final")],
        [InlineKeyboardButton(text="❌ Отменить заявку", callback_data="home")],
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def priority_button():
    buttons = [
        [InlineKeyboardButton(text="💎 Vip приоритет", callback_data="priority_vip")],
        [InlineKeyboardButton(text="🟢 Обычный приоритет", callback_data="priority_normal")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="buy"),
         InlineKeyboardButton(text="📜 Главное меню", callback_data="home")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def vip_payment_button():
    from src.utils.payment_methods import get_payment_methods
    methods = get_payment_methods()
    buttons = []
    for method in methods:
        buttons.append([InlineKeyboardButton(text=method["name"], callback_data=method["callback"])])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="buy"),
                    InlineKeyboardButton(text="📜 Главное меню", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def order_buttons(order_id: str):
    buttons = [
        [InlineKeyboardButton(text="📊 Статус очереди", callback_data=f"order_status_{order_id}")],
        [InlineKeyboardButton(text="❌ Отменить заявку", callback_data=f"order_cancel_{order_id}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def home_button():
    buttons = [
        [InlineKeyboardButton(text="👨‍💻 Оператор", url="https://t.me/scoody_op")],

        [InlineKeyboardButton(text="📜 Главное меню", callback_data="home")],

    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)
