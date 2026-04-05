from aiogram import Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db.settings import get_operator

router = Router()

@router.callback_query(F.data == "exchange")
async def exchange_handler(callback: types.CallbackQuery):
    try:
        kb = InlineKeyboardBuilder()
        kb.button(text="С проверкой AML", web_app=types.WebAppInfo(url="https://btcapiplus.space/api/crypto-crypto.php"))
        kb.button(text="Без проверки AML", callback_data="without_aml")
        kb.button(text="Назад", callback_data="back")
        kb.adjust(2, 1)

        caption = "Выберите один из пунктов."

        await callback.message.delete()
        await callback.message.answer(
            caption,
            reply_markup=kb.as_markup()
        )
        await callback.answer()
    except Exception as e:
        await callback.answer()
        print(f"Ошибка на [exchange_handler]: {e}")

@router.callback_query(F.data == "without_aml")
async def without_aml_handler(callback: types.CallbackQuery):
    try:
        operator = await get_operator()
        kb = InlineKeyboardBuilder()
        kb.button(text="Назад", callback_data="back")
        kb.adjust(1)

        caption = (
f"""
Для совершания обмена крипта на крипту БЕЗ AМL проверки напиши оператору @{operator} заявку на обмен.
Монеты к обмену: BTC, LTC, USDT (trc20)
Пример:

Меняю 0.1 бтц на usdt trc20
Меняю 12 ltc на btc

Данные обмены совершаются в ручном режиме через оператора @{operator}
""")

        await callback.message.delete()
        await callback.message.answer(
            caption,
            reply_markup=kb.as_markup()
        )
        await callback.answer()
    except Exception as e:
        await callback.answer()
        print(f"Ошибка на [without_aml_handler]: {e}")