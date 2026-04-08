from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from handlers.buy_base import show_payment_methods

router = Router()

@router.message(F.text == "🚀 Купить XMR (Monero)")
async def buy_xmr_handler(message: Message, edit: bool = False):
    msg = "Покупка Monero (XMR)"

    kb = InlineKeyboardBuilder()
    kb.button(text="✈️ Купить XMR", callback_data="buy_xmr_standard")
    kb.adjust(1)

    if edit:
        await message.edit_text(msg, reply_markup=kb.as_markup())
    else:
        await message.answer(msg, reply_markup=kb.as_markup())

@router.callback_query(F.data == "buy_xmr_standard")
async def handle_xmr_standard(callback: CallbackQuery, state: FSMContext):
    await show_payment_methods(callback, "xmr", {}, edit=True)
    await state.clear()

@router.callback_query(F.data == "back_to_buy_xmr")
async def back_to_buy_xmr(callback: CallbackQuery, state: FSMContext):
    await buy_xmr_handler(callback.message, edit=True)
    await state.clear()
    await callback.answer()
