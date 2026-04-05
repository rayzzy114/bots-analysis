from aiogram import Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import FSInputFile, InputMediaPhoto

router = Router()

@router.callback_query(F.data.startswith("wallet"))
async def wallet_handler(callback: types.CallbackQuery):
    try:
        kb = InlineKeyboardBuilder()
        kb.button(text="Пополнить", callback_data="deposit")
        kb.button(text="Вывод средств", callback_data="withdraw")
        kb.button(text="Купить", callback_data="buy")
        kb.button(text="Продать", callback_data="sell")
        kb.button(text="Обмен", callback_data="exchange_wallet")
        kb.button(text="Назад", callback_data="back")
        kb.adjust(2, 2, 1, 1)

        caption = (
            "<b>💼 Кошелек</b>\n\n"
            "Баланс: 0.0000000000 BTC\n"
            "Баланс: 0.0000000000 LTC\n"
            "Баланс: 0.0000000000 USDT TRC\n"
            "Примерно: 0.00 RUB"
        )
        try:
            await callback.message.edit_media(
                media=InputMediaPhoto(
                media=FSInputFile("media/wallet.jpg"),
                caption=caption
                ),
                reply_markup=kb.as_markup()
            )
        except Exception:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=FSInputFile("media/wallet.jpg"),
                caption=caption,
                reply_markup=kb.as_markup()
            )
    
        await callback.answer()
    except Exception as e:
        await callback.answer()
        print(f"Ошибка на [wallet_handler]: {e}")
