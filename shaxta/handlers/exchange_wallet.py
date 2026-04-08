def parse_amount(text: str) -> float | None:
    try:
        return float(text.replace(",", ".").replace(" ", ""))
    except Exception:
        return None
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import EXCHANGE_LIMIT_BTC, EXCHANGE_LIMIT_LTC, EXCHANGE_LIMIT_USDT

router = Router()

@router.callback_query(F.data == "exchange_wallet")
async def exchange_wallet_handler(callback: types.CallbackQuery):
    try:
        await callback.message.delete()

        kb = InlineKeyboardBuilder()
        kb.button(text="BTC", callback_data="exchange_btc")
        kb.button(text="LTC", callback_data="exchange_ltc")
        kb.button(text="USDT TRC", callback_data="exchange_usdt")
        kb.button(text="Главная меню", callback_data="back")
        kb.adjust(2, 1)

        text = "Выберите монету которую хотите обменять."

        await callback.message.answer(
            text,
            reply_markup=kb.as_markup()
        )

        await callback.answer()
    except Exception as e:
        await callback.answer()
        print(f"Ошибка в [exchange_wallet_handler]: {e}")

@router.callback_query(F.data.in_({"exchange_btc", "exchange_ltc", "exchange_usdt"}))
async def specific_exchange_handler(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.delete()

        currency = callback.data.split("_")[1].upper()

        if currency == "BTC":
            other_currencies = ["LTC", "USDT"]
        elif currency == "LTC":
            other_currencies = ["BTC", "USDT"]
        else:
            other_currencies = ["BTC", "LTC"]

        kb = InlineKeyboardBuilder()
        for curr in other_currencies:
            kb.button(text=curr, callback_data=f"specific_exchange_{curr.lower()}")
        kb.button(text="Главная меню", callback_data="back")
        kb.adjust(2, 1)

        text = "Выберите монету которую хотите получить"

        await callback.message.answer(
            text,
            reply_markup=kb.as_markup()
        )

        await callback.answer()
    except Exception as e:
        await callback.answer()
        print(f"Ошибка в [specific_exchange_handler]: {e}")

@router.callback_query(F.data.in_({"specific_exchange_btc", "specific_exchange_ltc", "specific_exchange_usdt"}))
async def final_exchange_handler(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.delete()

        target_currency = callback.data.split("_")[2].upper()

        kb = InlineKeyboardBuilder()
        kb.button(text="Главная меню", callback_data="back")
        kb.adjust(1)

        limit = {
            "BTC": EXCHANGE_LIMIT_BTC,
            "LTC": EXCHANGE_LIMIT_LTC,
            "USDT": EXCHANGE_LIMIT_USDT,
        }

        currency_limit = limit.get(target_currency, "неизвестно")

        text = (
            f"Выберите количество {target_currency} которое хотите обменять\n\n"
            f"Лимит обмена: <code>{currency_limit}</code> <b>{target_currency}</b>"
        )

        await state.update_data(target_currency=target_currency)

        await callback.message.answer(text, reply_markup=kb.as_markup())

        await callback.answer()
    except Exception as e:
        await callback.answer()
        print(f"Ошибка в [final_exchange_handler]: {e}")

@router.message(F.text)
async def handle_amount_input(message: types.Message, state: FSMContext):
    try:
        data = await state.get_data()
        target_currency = data.get('target_currency')

        if not target_currency:
            return

        try:
            float(message.text.replace(',', '.'))
        except ValueError:
            await message.answer("Пожалуйста, введите корректное число.")
            return

        kb = InlineKeyboardBuilder()
        kb.button(text="Главная меню", callback_data="back")

        await message.answer(
            "Недостаточно средств на балансе, для обмена!\n\n"
            f"Баланс: <code>0</code> <b>{target_currency}</b>\n",
            reply_markup=kb.as_markup()
        )

        await state.clear()

    except Exception as e:
        print(f"Ошибка в [handle_amount_input]: {e}")
        await message.answer("Произошла ошибка при обработке запроса.")
