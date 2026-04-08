from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from src.admin_panel import get_admin_context


def home_btn():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📈 Купить"),
                KeyboardButton(text="📉 Продать")
            ],
            [
                KeyboardButton(text="🛒 Готовые обмены")
            ],
            [
                KeyboardButton(text="🧮 Калькулятор")
            ],
            [
                KeyboardButton(text="💻 Личный кабинет"),
                KeyboardButton(text="📱 Контакты")
            ]
        ],
        resize_keyboard=True
    )
    return keyboard



def profile_btn():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="Кошелек"),
                KeyboardButton(text="Промокод")
            ],
            [
                KeyboardButton(text="🛒 Готовые обмены")
            ],
            [
                KeyboardButton(text="🧮 Калькулятор")
            ],
            [
                KeyboardButton(text="💻 Личный кабинет"),
                KeyboardButton(text="📱 Контакты")
            ]
        ],
        resize_keyboard=True
    )
    return keyboard


def calc_btn():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="BTC"),
                KeyboardButton(text="LTC"),
                KeyboardButton(text="XMR"),
                KeyboardButton(text="USDT")
            ],
            [
                KeyboardButton(text="❌ Отмена")
            ],

        ],
        resize_keyboard=True
    )
    return keyboard


def buy_btn():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🔄 BTC"),
                KeyboardButton(text="🔄 LTC"),
            ],
            [
                KeyboardButton(text="🔄 XMR"),
                KeyboardButton(text="🔄 USDT")
            ],
            [
                KeyboardButton(text="⬅️ Назад")
            ],

        ],
        resize_keyboard=True
    )
    return keyboard


def sale_btn():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="Продать BTC"),
                KeyboardButton(text="Продать LTC"),
            ],
            [
                KeyboardButton(text="Продать XMR"),
                KeyboardButton(text="Продать USDT")
            ],
            [
                KeyboardButton(text="⬅️ Назад")
            ],

        ],
        resize_keyboard=True
    )
    return keyboard


def buy_btn_finish():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="❌ Отмена")
            ],

        ],
        resize_keyboard=True
    )
    return keyboard


def sale_btn_finish():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="✅ Продолжить"),
                KeyboardButton(text="❌ Отмена")
            ],

        ],
        resize_keyboard=True
    )
    return keyboard



def buy_card_btn(final_price: float | None = None):
    ctx = get_admin_context()
    methods = (
        ctx.settings.payment_methods()
        if ctx is not None
        else ["Карта", "СПБ", "Альфа-Альфа", "Сбер-Сбер", "Озон-Озон", "ТБанк-Тбанк", "Сбер QR", "Перевод SIM"]
    )
    suffix = ""
    if isinstance(final_price, (int, float)):
        suffix = f" ({int(round(float(final_price)))} руб.)"
    buttons = [
        [InlineKeyboardButton(text=f"{method}{suffix}", callback_data=f"pay_method_{index}")]
        for index, method in enumerate(methods)
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
