from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def buy_button_operation(crypto=False, currency="btc"):
    currency_display = currency.upper()
    buttons = [
        [
            InlineKeyboardButton(text="Калькулятор", switch_inline_query_current_chat=f"calc_{currency} "),
            InlineKeyboardButton(
                text=f"В {currency_display}" if crypto else "В рублях",
                callback_data="operation_buy_crypto" if crypto else "operation_buy_ru"
            )],
        [InlineKeyboardButton(text="🔙 Вернуться", callback_data="buy"),
         InlineKeyboardButton(text="🚀 Главное меню", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def button_buy_back():
    buttons = [
        [InlineKeyboardButton(text="🔙 Вернуться", callback_data="buy")],
        [InlineKeyboardButton(text="🚀 Главное меню", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def vip_payment_button():
    from src.db.settings import get_payment_methods
    methods = await get_payment_methods()
    buttons = []
    for i, method in enumerate(methods):
        buttons.append([InlineKeyboardButton(text=method["name"], callback_data=f"payment_method_{i}")])
    buttons.append([InlineKeyboardButton(text="🔙 Вернуться", callback_data="buy"),
                    InlineKeyboardButton(text="🚀 Главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def order_buttons(order_id: str):
    buttons = [
        [InlineKeyboardButton(text="❌ Отменить заявку", callback_data=f"order_cancel_{order_id}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def payment_details_buttons(order_id: str):
    buttons = [
        [InlineKeyboardButton(text="✅ Начать обмен", callback_data=f"start_exchange_{order_id}")],
        [InlineKeyboardButton(text="🔙 Вернуться", callback_data="buy"),
         InlineKeyboardButton(text="🚀 Главное меню", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def requisites_action_buttons():
    buttons = [
        [InlineKeyboardButton(text="✅ Оплатил", callback_data="requisites_paid"),
         InlineKeyboardButton(text="🚫 Отменить", callback_data="requisites_cancel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

