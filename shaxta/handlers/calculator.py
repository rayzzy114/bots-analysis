from aiogram import F, Router, types
from aiogram.filters.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db.settings import get_commission
from utils.amount_input import parse_amount_value
from utils.exchange_rates import exchange_rates

router = Router()


class CalculatorState(StatesGroup):
    waiting_amount = State()


async def get_calculator_rate(
    currency: str,
    direction: str,
    force_update: bool = False,
) -> tuple[float, float]:
    commission = await get_commission()
    rates = await exchange_rates.get_trade_rates(
        commission,
        force_update=force_update,
        max_age_seconds=120,
    )
    side = "buy" if direction == "buy" else "sell"
    rate = rates.get(currency, {}).get(side)
    if not rate or rate <= 0:
        raise ValueError(f"Курс {currency} недоступен")
    return rate, commission


@router.callback_query(F.data == "calculator")
async def calculator_handler(callback: types.CallbackQuery, state: FSMContext):
    try:
        await state.clear()

        kb = InlineKeyboardBuilder()
        kb.button(text="Покупка (RUB -> CRYPTO)", callback_data="calc_mode_buy")
        kb.button(text="Продажа (CRYPTO -> RUB)", callback_data="calc_mode_sell")
        kb.button(text="Назад", callback_data="back")
        kb.adjust(1)

        caption = "<b>Калькулятор валют</b>\n\nВыберите тип операции:"

        try:
            await callback.message.edit_media(
                media=InputMediaPhoto(
                    media=FSInputFile("media/calculator.jpg"),
                    caption=caption,
                ),
                reply_markup=kb.as_markup(),
            )
        except Exception:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=FSInputFile("media/calculator.jpg"),
                caption=caption,
                reply_markup=kb.as_markup(),
            )
        await callback.answer()
    except Exception as error:
        await callback.answer()
        print(f"Ошибка на [calculator_handler]: {error}")


@router.callback_query(F.data.in_({"calc_mode_buy", "calc_mode_sell"}))
async def calculator_mode_handler(callback: types.CallbackQuery, state: FSMContext):
    try:
        direction = "buy" if callback.data == "calc_mode_buy" else "sell"
        await state.update_data(direction=direction)

        kb = InlineKeyboardBuilder()
        kb.button(text="BTC", callback_data="calc_currency_btc")
        kb.button(text="LTC", callback_data="calc_currency_ltc")
        kb.button(text="ETH", callback_data="calc_currency_eth")
        kb.button(text="USDT TRC", callback_data="calc_currency_usdt")
        kb.button(text="Назад", callback_data="calculator")
        kb.adjust(2, 2, 1)

        await callback.message.delete()
        await callback.message.answer("Выберите валюту:", reply_markup=kb.as_markup())
        await callback.answer()
    except Exception as error:
        await callback.answer()
        print(f"Ошибка на [calculator_mode_handler]: {error}")


@router.callback_query(F.data.in_({"calc_currency_btc", "calc_currency_ltc", "calc_currency_eth", "calc_currency_usdt"}))
async def calculator_currency_handler(callback: types.CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        direction = data.get("direction")
        if direction not in {"buy", "sell"}:
            await callback.answer("Сначала выберите тип операции", show_alert=True)
            return

        currency = callback.data.split("_")[-1].upper()
        rate, commission = await get_calculator_rate(currency, direction)
        await state.update_data(currency=currency, rate=rate)

        kb = InlineKeyboardBuilder()
        kb.button(text="Назад", callback_data="calculator")
        kb.adjust(1)

        direction_label = "Покупка" if direction == "buy" else "Продажа"
        caption = (
            f"<b>{direction_label} {currency}</b>\n\n"
            f"Текущий курс: <b>1 {currency} = {rate:,.2f} RUB</b>\n"
            f"Комиссия сервиса: <b>{commission:.2f}%</b>\n\n"
            "Введите сумму: с точкой (например 0.001) это крипта, без точки это рубли."
        )

        await callback.message.delete()
        await callback.message.answer(caption, reply_markup=kb.as_markup())
        await state.set_state(CalculatorState.waiting_amount)
        await callback.answer()
    except Exception as error:
        await callback.answer("Курс временно недоступен", show_alert=True)
        print(f"Ошибка на [calculator_currency_handler]: {error}")


@router.message(CalculatorState.waiting_amount)
async def calculator_amount_handler(message: types.Message, state: FSMContext):
    try:
        data = await state.get_data()
        direction = data.get("direction")
        currency = data.get("currency")
        if direction not in {"buy", "sell"} or not currency:
            await state.clear()
            await message.answer("❌ Сценарий сброшен. Откройте калькулятор заново.")
            return

        try:
            amount, is_crypto = parse_amount_value(message.text)
        except ValueError:
            await message.answer("❌ Введите числовое значение")
            return

        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше нуля")
            return

        rate, commission = await get_calculator_rate(currency, direction)
        if is_crypto:
            crypto_amount = amount
            rub_amount = crypto_amount * rate
        else:
            rub_amount = amount
            crypto_amount = rub_amount / rate

        direction_label = "покупки" if direction == "buy" else "продажи"
        result_text = (
            f"<b>Результат расчета ({direction_label})</b>\n\n"
            f"Курс: <b>1 {currency} = {rate:,.2f} RUB</b>\n"
            f"Комиссия сервиса: <b>{commission:.2f}%</b>\n\n"
            f"💵 В RUB: <b>{rub_amount:,.2f}</b>\n"
            f"💎 В {currency}: <b>{crypto_amount:.8f}</b>"
        )

        kb = InlineKeyboardBuilder()
        kb.button(text="Новый расчет", callback_data="calculator")
        kb.button(text="Назад", callback_data="back")
        kb.adjust(1)

        await state.clear()
        await message.answer(result_text, reply_markup=kb.as_markup())
    except Exception as error:
        print(f"Ошибка на [calculator_amount_handler]: {error}")
        await message.answer("❌ Произошла ошибка. Попробуйте еще раз.")
