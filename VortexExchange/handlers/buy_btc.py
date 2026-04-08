from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from handlers.buy_base import show_payment_methods

router = Router()

async def buy_btc(message: Message, edit: bool = False):
    msg = "Выберите направление: "

    kb = InlineKeyboardBuilder()
    kb.button(text="✈️ Обычный BTC", callback_data="buy_btc_standard")
    kb.button(text="🤖 BTC на bigmafiabot", callback_data="none")
    kb.adjust(1)

    if edit:
        await message.edit_text(msg, reply_markup=kb.as_markup())
    else:
        await message.answer(msg, reply_markup=kb.as_markup())

@router.message(F.text == "🚀 Купить BTC")
async def buy_btc_handler(message: Message):
    await buy_btc(message)

@router.callback_query(F.data == "back_to_buy_btc")
async def back_to_buy_btc(callback: CallbackQuery, state: FSMContext):
    await buy_btc(callback.message, edit=True)
    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "buy_btc_standard")
async def handle_btc_standard(callback: CallbackQuery, state: FSMContext):
    await show_payment_methods(callback, "btc", {}, edit=True)
    await state.clear()
