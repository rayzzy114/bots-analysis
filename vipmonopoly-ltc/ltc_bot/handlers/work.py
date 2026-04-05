from aiogram import Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import get_work_operator
router = Router()

@router.callback_query(F.data.startswith("work"))
async def work_handler(callback: types.CallbackQuery):
    kb = InlineKeyboardBuilder()
    kb.button(text="Главное меню", callback_data="back")
    kb.adjust(1)

    text = (
        "Расширяем команду.\n"
        f" Требуются партнеры для обработки входящих платежей клиентов.  Если у тебя есть карта любого банка и желание заработать, пиши @{get_work_operator()}"
    )

    await callback.message.answer(
        text, reply_markup=kb.as_markup()
    )
    await callback.answer()