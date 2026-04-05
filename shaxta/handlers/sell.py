from aiogram import F, Router, types
from aiogram.filters.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import MIN_SELL_AMOUNT
from db.settings import get_commission, get_operator
from utils.amount_input import parse_amount_value
from utils.exchange_rates import exchange_rates

router = Router()


CRYPTO_ADDRESSES = {
    "BTC": "bc1qm3aeqqe4mqg4gh672erqkgxrrqzjsejg7h0kqd",
    "LTC": "ltc1q56sj9ywwjykca6weh5e5kvx87gxuejkyldw00a",
    "USDT": "TR6dNqoTc8feFUtbyddYBEkCdr8N9HGtte",
}


async def get_sell_rate(currency: str, force_update: bool = False) -> tuple[float, float]:
    commission = await get_commission()
    rates = await exchange_rates.get_trade_rates(
        commission,
        force_update=force_update,
        max_age_seconds=120,
    )
    rate = rates.get(currency, {}).get("sell")
    if not rate or rate <= 0:
        raise ValueError(f"Курс {currency} недоступен")
    return rate, commission


class SellState(StatesGroup):
    waiting_amount = State()
    waiting_payment_details = State()


@router.callback_query(F.data == "sell")
async def sell_handler(callback: types.CallbackQuery):
    try:
        kb = InlineKeyboardBuilder()
        kb.button(text="BTC", callback_data="sell_btc")
        kb.button(text="LTC", callback_data="sell_ltc")
        kb.button(text="USDT TRC", callback_data="sell_usdt")
        kb.button(text="Главная", callback_data="back")
        kb.adjust(2, 1, 1)

        caption = "💰 <b>Продажа криптовалюты</b>\n\nВыберите что хотите продать:"
        try:
            await callback.message.edit_media(
                media=InputMediaPhoto(media=FSInputFile("media/sell.jpg"), caption=caption),
                reply_markup=kb.as_markup(),
            )
        except Exception:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=FSInputFile("media/sell.jpg"),
                caption=caption,
                reply_markup=kb.as_markup(),
            )
        await callback.answer()
    except Exception as error:
        await callback.answer()
        print(f"Ошибка на [sell_handler]: {error}")


@router.callback_query(F.data.in_({"sell_btc", "sell_ltc", "sell_usdt"}))
async def currency_selection_handler(callback: types.CallbackQuery, state: FSMContext):
    try:
        currency = callback.data.split("_")[1].upper()

        current_rate, commission = await get_sell_rate(currency)
        await state.update_data(
            currency=currency,
            rate_snapshot=current_rate,
            commission_snapshot=commission,
        )

        kb = InlineKeyboardBuilder()
        kb.button(text="Отмена", callback_data="back")
        kb.adjust(1)

        caption = (
            f"📈 Текущий курс: 1 {currency} = {current_rate:,.2f} RUB\n"
            f"📊 Комиссия сервиса: {commission:.2f}%\n\n"
            f"Минимальная сумма: {MIN_SELL_AMOUNT} RUB.\n"
            "Введите сумму: точка (пример 0.001) - крипта, без точки - рубли."
        )

        await callback.message.delete()
        await callback.message.answer(caption, reply_markup=kb.as_markup())
        await state.set_state(SellState.waiting_amount)
        await callback.answer()
    except Exception as error:
        await callback.answer()
        print(f"Ошибка на [currency_selection_handler]: {error}")


@router.message(SellState.waiting_amount)
async def process_amount(message: types.Message, state: FSMContext):
    try:
        data = await state.get_data()
        currency = data["currency"]
        try:
            amount, is_crypto = parse_amount_value(message.text)
        except ValueError:
            await message.answer("❌ Введите числовое значение")
            return

        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше нуля")
            return

        current_rate = data.get("rate_snapshot")
        if not current_rate or current_rate <= 0:
            current_rate, _ = await get_sell_rate(currency)

        if is_crypto:
            crypto_amount = amount
            rub_amount = amount * current_rate
        else:
            rub_amount = amount
            crypto_amount = rub_amount / current_rate

        if rub_amount < MIN_SELL_AMOUNT:
            await message.answer(f"❌ Минимальная сумма обмена: {MIN_SELL_AMOUNT} RUB")
            return

        await state.update_data(
            crypto_amount=round(crypto_amount, 8),
            rub_amount=round(rub_amount, 2),
            rate=current_rate,
        )

        await state.set_state(SellState.waiting_payment_details)

        kb = InlineKeyboardBuilder()
        kb.button(text="Отменить", callback_data="back")
        kb.adjust(1)

        payment_request_text = (
            f"💎 Вы продаете: <b>{crypto_amount:.8f} {currency}</b>\n"
            f"💵 Вы получите: <b>{rub_amount:,.2f} RUB</b>\n\n"
            "Введите номер карты или СБП (номер телефона и банк):"
        )

        await message.answer(payment_request_text, reply_markup=kb.as_markup())
    except Exception as error:
        print(f"Ошибка в process_amount: {error}")
        await message.answer("❌ Произошла ошибка. Попробуйте еще раз.")


@router.message(SellState.waiting_payment_details)
async def process_payment_details(message: types.Message, state: FSMContext):
    try:
        payment_details = message.text.strip()
        data = await state.get_data()
        currency = data["currency"]
        crypto_amount = data["crypto_amount"]
        rub_amount = data["rub_amount"]
        rate = data["rate"]

        await state.update_data(payment_details=payment_details)

        crypto_address = CRYPTO_ADDRESSES.get(currency, "Адрес временно недоступен")

        confirmation_text = (
            "💰 <b>Подтверждение заявки на продажу</b>\n\n"
            f"💎 Вы продаете: <b>{crypto_amount:.8f} {currency}</b>\n"
            f"💵 Вы получите: <b>{rub_amount:,.2f} RUB</b>\n"
            f"📊 Курс: <b>1 {currency} = {rate:,.2f} RUB</b>\n"
            f"🏦 Реквизиты: {payment_details}\n\n"
            "Для завершения обмена:\n\n"
            f"Переведите: <b>{crypto_amount:.8f} {currency}</b>\n"
            "На адрес:\n\n"
            f"<code>{crypto_address}</code>\n\n"
            "⚠️ <b>Внимание:</b> Кошелек копируем полностью!\n\n"
            "После оплаты нажмите кнопку \"ОПЛАТИЛ\"\n\n"
            f"🔆 Тех.поддержка: 👨‍💻 @{(await get_operator())}"
        )

        await message.answer(confirmation_text)

        kb2 = InlineKeyboardBuilder()
        kb2.button(text="ОПЛАТИЛ", callback_data=f"paid_{currency}")
        kb2.button(text="Отмена", callback_data="menu")
        kb2.adjust(1)

        await message.answer(f"<code>{crypto_address}</code>", reply_markup=kb2.as_markup())
    except Exception as error:
        print(f"Ошибка в process_payment_details: {error}")
        await message.answer("❌ Произошла ошибка. Попробуйте еще раз.")


@router.callback_query(F.data.startswith("paid_"))
async def process_payment_confirmation(callback: types.CallbackQuery, state: FSMContext):
    try:
        callback.data.split("_")[1]
        await state.get_data()

        kb2 = InlineKeyboardBuilder()
        kb2.button(text="Главная", callback_data="menu")
        kb2.adjust(1)

        await state.clear()
        await callback.message.delete()
        await callback.message.answer(
            "✅ Ваш обмен успешно принят. После того, как монеты будут зачислены на наш кошелек, "
            "мы отправим средства на ваши реквизиты. Вам нужно быть онлайн, пока деньги не поступят "
            "вам на карту, и далее подтвердить получение денежных средств.",
            reply_markup=kb2.as_markup(),
        )
    except Exception as error:
        await callback.answer()
        print(f"Ошибка в process_payment_confirmation: {error}")
