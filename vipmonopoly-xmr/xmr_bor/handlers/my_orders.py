from aiogram import Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

router = Router()

@router.callback_query(F.data.startswith("my_orders"))
async def rules_handler(callback: types.CallbackQuery):
    kb = InlineKeyboardBuilder()
    kb.button(text="Главное меню", callback_data="back")
    kb.adjust(1)

    text = (
        "В настощий момент у вас нет ни одного заказа."
    )

    await callback.message.answer(
        text, reply_markup=kb.as_markup()
    )
    await callback.answer()