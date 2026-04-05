from aiogram import types, Router
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import Message
from config import operator, rates, sell_btc, news_channel, BOT_USER_LTC, BOT_USER_XMR

from db.user import add_user

router = Router()

async def send_start(message: types.Message, edit: bool = False):
    user_id = message.from_user.id
    
    await add_user(user_id)

    kb = InlineKeyboardBuilder()
    kb.button(text="👉🏻 Купить BTC 👈🏻", callback_data="buy_btc")
    kb.button(text="⚡ Купить LTC ⚡", url=f"https://t.me/{BOT_USER_LTC}")
    kb.button(text="♻️ Купить XMR ♻️", url=f"https://t.me/{BOT_USER_XMR}")
    kb.button(text="Промокод", callback_data="promo")
    kb.button(text="👤 Партнерская программа", callback_data="partner")
    kb.button(text="Поддержка / Оператор", url=f"https://t.me/{operator}")
    kb.button(text="Отзывы", url=f"https://t.me/{rates}")
    kb.button(text="Мои заказы", callback_data="my_orders")
    kb.button(text="Правила", callback_data="rules")
    kb.button(text="💰 Работа 💰", callback_data="work")
    kb.button(text="Продать биткоин", url=f"https://t.me/{sell_btc}")
    kb.button(text="Новостной канал", url=f"https://t.me/{news_channel}")
    kb.adjust(1, 1, 1, 2, 2, 1, 1, 1, 1)

    caption = (
        "<b>Бот обменник</b>\n\n"
        "Тут ты можешь обменять свои <b>RUB</b> на <b>BTC</b>\n\n"
        """Жми кнопку "<b>👉🏻 Купить BTC 👈🏻</b>" или просто введи сумму в RUB или BTC\n\n"""
        "Пример: <b>0.01</b> или <b>0,01</b> или <b>5030</b>"
    )

    if edit:
        await message.edit_text(
            text=caption,
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            text=caption,
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )

@router.message(Command("start"))
async def start_with_check(message: Message):
    await send_start(message)