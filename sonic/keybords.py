from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from config import URL_INFO


def kb_start():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Правила и соглашение SoNic Ex", url=URL_INFO)],
        [
            InlineKeyboardButton(text="Я согласен", callback_data="App|yes"),
            InlineKeyboardButton(text="Не согласен", callback_data="App|no"),
        ],
    ])
    return keyboard


def kb_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Купить Bitcoin (BTC)"), KeyboardButton(text="Купить Litecoin (LTC)")],
            [KeyboardButton(text="👤Мой кошелек👤")],
            [KeyboardButton(text="🔗ПАРТНЕРКА🔗"), KeyboardButton(text="📉Продать криптовалюту📉 ")],
            [KeyboardButton(text="🧮Калькулятор🧮")],
            [KeyboardButton(text="📜Правила📜"), KeyboardButton(text="🗃Отзывы🗃")],
            [KeyboardButton(text="👨‍💻Оператор👨‍💻")],
        ],
        resize_keyboard=True,
    )
    return keyboard


def kb_no_app():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Обновить")]],
        resize_keyboard=True,
    )
    return keyboard


def kb_cancel_input():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Отмена")]],
        resize_keyboard=True,
    )
    return keyboard


def kb_pay_go():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Перейти к сделке", callback_data="Go"),
            InlineKeyboardButton(text="Отмена", callback_data="cancel"),
        ],
    ])
    return keyboard


def kb_adress_go():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Подтвердить", callback_data="AdressGO"),
            InlineKeyboardButton(text="Отмена", callback_data="cancel"),
        ],
    ])
    return keyboard


def kb_promokod_go():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ВВЕСТИ ПРОМО-КОД", callback_data="promo_null")],
        [
            InlineKeyboardButton(text="Перейти к оплате", callback_data="payments"),
            InlineKeyboardButton(text="Отмена", callback_data="cancel"),
        ],
    ])
    return keyboard


def kb_payments_success():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я оплатил(а)", callback_data="Finish_pay")],
        [InlineKeyboardButton(text="❌ Отменить заявку", callback_data="cancel")],
    ])
    return keyboard


def kb_home_finish():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="На главную", callback_data="cancel")],
    ])
    return keyboard


def kb_my_wallet():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📤Отправить📤"), KeyboardButton(text="📥Пополнить📥")],
            [KeyboardButton(text="🏠В главное меню🏠")],
        ],
        resize_keyboard=True,
    )
    return keyboard


def kb_pay_money_Wallet():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Купить Bitcoin (BTC)"), KeyboardButton(text="Купить Litecoin (LTC)")],
            [KeyboardButton(text="👤Мой кошелек👤")],
            [KeyboardButton(text="🏠В главное меню🏠")],
        ],
        resize_keyboard=True,
    )
    return keyboard


def kb_parthers():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🤑 Вывод средств 🤑")],
            [KeyboardButton(text="🏠В главное меню🏠")],
        ],
        resize_keyboard=True,
    )
    return keyboard


def kb_one_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🏠В главное меню🏠")]],
        resize_keyboard=True,
    )
    return keyboard


def kb_calkulate():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🧮BTC"), KeyboardButton(text="🧮LTC")],
            [KeyboardButton(text="Отмена")],
        ],
        resize_keyboard=True,
    )
    return keyboard


def ikb_menu_admin():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Изменить VISA")],
            [KeyboardButton(text="Изменить СБП")],
            [KeyboardButton(text="Выход")],
        ],
        resize_keyboard=True,
    )
    return keyboard


def ikb_stop_admin():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Выйти из режима ввода")]],
        resize_keyboard=True,
    )
    return keyboard
