from aiogram import types, Router, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardMarkup
from aiogram.types import Message, CallbackQuery
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from utils.escape_html import escape_html
from config import BOT_NAME, NEWS_LINK

router = Router()

async def send_start(message: Message, user_id):
    """ await add_user(user_id) """

    msg1 = (
        f"Добро пожаловать в <b>{escape_html(BOT_NAME)}</b>!"
    )

    msg2 = (
        f"❗ Перед использованием ОБЯЗАТЕЛЬНО прочти раздел «FAQ»\n"
        f"❗ Так же подпишитесь на наш новостной канал, чтобы быть в курсе анонсов и розыгрышей."
    )
    

    kb1 = ReplyKeyboardMarkup(
        keyboard=[
            [
                types.KeyboardButton(text="🚀 Купить BTC"), types.KeyboardButton(text="🚀 Купить XMR (Monero)"),
            ],
            [
                types.KeyboardButton(text="💰 Продать BTC/XMR"), types.KeyboardButton(text="🏠 Личный кабинет"),
            ],
            [
                types.KeyboardButton(text="🎁Ежедневный бонус🎁"),
            ],
            [
                types.KeyboardButton(text="👩🏻‍💻 Тех. Поддержка")
            ]
        ],
        resize_keyboard=True
    )

    kb2 = InlineKeyboardBuilder()
    kb2.button(
        text="📚 FAQ",
        callback_data="faq"
    )
    kb2.button(
        text="💎 Канал",
        url=f"https://t.me/{NEWS_LINK}"
    )
    kb2.adjust(1)

    await message.answer(
        text=msg1, reply_markup=kb1
    )

    await message.answer(
        text=msg2,
        reply_markup=kb2.as_markup()
    )

@router.callback_query(F.data == "start_handler")
async def start_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.delete()
    except:
        pass
    
    user_id = callback.from_user.id
    await send_start(callback.message, user_id)
    await callback.answer()

@router.message(Command("start"))
async def start(message: Message):
    user_id = message.from_user.id
    await send_start(message, user_id)