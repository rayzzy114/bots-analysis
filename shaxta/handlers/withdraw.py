from aiogram import Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import MIN_WITHDRAW_AMOUNT

router = Router()

@router.callback_query(F.data.startswith("withdraw"))
async def withdraw_handler(callback: types.CallbackQuery):
    try:
        kb = InlineKeyboardBuilder()
        kb.button(text="Главная", callback_data="menu")
        kb.adjust(1)

        (await callback.bot.get_me()).username

        caption = (
            "К сожалению, у вас недостаточный баланс для вывода средств.\n\n"
            f"<b>Минимум – {MIN_WITHDRAW_AMOUNT} руб.</b>"
        )
        await callback.message.delete()
        await callback.message.answer(
            caption,
            reply_markup=kb.as_markup()
        )
        await callback.answer()
    except Exception as e:
        await callback.answer()
        print(f"Ошибка на [withdraw_handler]: {e}")