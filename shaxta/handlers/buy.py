import asyncio
import random

from aiogram import F, Router, types
from aiogram.filters.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import BOT_NAME, MIN_BUY_AMOUNT
from db.settings import get_bank, get_commission, get_operator, get_requisites
from utils.amount_input import parse_amount_value
from utils.exchange_rates import exchange_rates

router = Router()


class BuyState(StatesGroup):
    waiting_amount = State()
    waiting_address = State()


MIN_AMOUNT = MIN_BUY_AMOUNT


async def get_buy_rate(currency: str, force_update: bool = False) -> tuple[float, float]:
    commission = await get_commission()
    rates = await exchange_rates.get_trade_rates(
        commission,
        force_update=force_update,
        max_age_seconds=120,
    )
    rate = rates.get(currency, {}).get("buy")
    if not rate or rate <= 0:
        raise ValueError(f"Курс {currency} недоступен")
    return rate, commission


@router.callback_query(F.data == "buy")
async def buy_handler(callback: types.CallbackQuery):
    try:
        kb = InlineKeyboardBuilder()
        kb.button(text="BTC", callback_data="buy_btc")
        kb.button(text="LTC", callback_data="buy_ltc")
        kb.button(text="ETH", callback_data="buy_eth")
        kb.button(text="USDT TRC", callback_data="buy_usdt")
        kb.button(text="Главная", callback_data="back")
        kb.adjust(2, 2, 1)

        caption = "Выберите что хотите купить."
        try:
            await callback.message.edit_media(
                media=InputMediaPhoto(media=FSInputFile("media/buy.jpg"), caption=caption),
                reply_markup=kb.as_markup(),
            )
        except Exception:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=FSInputFile("media/buy.jpg"),
                caption=caption,
                reply_markup=kb.as_markup(),
            )
        await callback.answer()
    except Exception as error:
        await callback.answer()
        print(f"Ошибка на [buy_handler]: {error}")


@router.callback_query(F.data.in_({"buy_btc", "buy_ltc", "buy_eth", "buy_usdt"}))
async def buy_currency_handler(callback: types.CallbackQuery, state: FSMContext):
    try:
        currency = callback.data.split("_")[1].upper()
        await state.update_data(currency=currency)

        kb = InlineKeyboardBuilder()
        kb.button(text="Карта", callback_data=f"method_{currency.lower()}_card")
        kb.button(text="СБП", callback_data=f"method_{currency.lower()}_sbp")
        kb.button(text="Отмена", callback_data="back")
        kb.adjust(2, 1)

        caption = (
            "Выберите способ оплаты\n"
            f"ВНИМАНИЕ: обмен от {MIN_AMOUNT} RUB\n"
            "Дорогие клиенты нашего обменника, нам все равно с каких банков вы будете платить на наши карты."
        )
        await callback.message.delete()
        await callback.message.answer(caption, reply_markup=kb.as_markup())
        await callback.answer()
    except Exception as error:
        await callback.answer()
        print(f"Ошибка на [buy_currency_handler]: {error}")


@router.callback_query(F.data.startswith("method_"))
async def payment_method_handler(callback: types.CallbackQuery, state: FSMContext):
    try:
        data_parts = callback.data.split("_")
        currency = data_parts[1].upper()
        payment_method = data_parts[2]

        current_rate, commission = await get_buy_rate(currency)

        await state.update_data(
            currency=currency,
            payment_method=payment_method,
            rate_snapshot=current_rate,
            commission_snapshot=commission,
        )

        kb = InlineKeyboardBuilder()
        kb.button(text="Отмена", callback_data="back")
        kb.adjust(1)

        caption = (
            f"📈 Текущий курс 1 {currency} = {current_rate:.1f} RUB\n"
            f"📊 Комиссия сервиса: {commission:.2f}%\n\n"
            f"Минимальный обмен: от {MIN_AMOUNT} RUB (от 500 при наличии купона)\n\n"
            f"👉 Укажите сумму в {currency}: 0.001 или 0,001\n"
            f"Или в RUB: {MIN_AMOUNT} или большее значение"
        )

        await callback.message.delete()
        await callback.message.answer(caption, reply_markup=kb.as_markup())
        await callback.answer()
        await state.set_state(BuyState.waiting_amount)
    except Exception as error:
        await callback.answer()
        print(f"Ошибка на [payment_method_handler]: {error}")


@router.message(BuyState.waiting_amount)
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
            current_rate, _ = await get_buy_rate(currency)

        if is_crypto:
            crypto_amount_final = amount
            rub_amount = amount * current_rate
        else:
            rub_amount = amount
            crypto_amount_final = rub_amount / current_rate

        if rub_amount < MIN_AMOUNT:
            await message.answer(f"❌ Минимальная сумма обмена: {MIN_AMOUNT} RUB")
            return

        await state.update_data(
            crypto_amount=round(crypto_amount_final, 8),
            rub_amount=round(rub_amount, 2),
            rate=current_rate,
        )

        await state.set_state(BuyState.waiting_address)

        kb = InlineKeyboardBuilder()
        kb.button(text="Отменить", callback_data="back")
        kb.adjust(1)

        address_request_text = (
            f"💵 Сумма к оплате: <b>{rub_amount:,.2f} RUB</b>\n"
            f"💎 К получению: <b>{crypto_amount_final:.8f} {currency}</b>\n\n"
            "Введите адрес кошелька для получения:"
        )

        await message.answer(address_request_text, reply_markup=kb.as_markup())
    except Exception as error:
        print(f"Ошибка в process_amount: {error}")
        await message.answer("❌ Попробуйте еще раз.")


@router.message(BuyState.waiting_address)
async def process_address(message: types.Message, state: FSMContext):
    try:
        address = message.text.strip()

        if len(address) < 10:
            await message.answer(
                "❌ Адрес слишком короткий. Пожалуйста, проверьте и введите корректный адрес:"
            )
            return

        data = await state.get_data()
        currency = data["currency"]
        crypto_amount = data["crypto_amount"]
        rub_amount = data["rub_amount"]
        rate = data["rate"]
        commission = data.get("commission_snapshot", 0.0)

        await state.update_data(address=address)

        kb = InlineKeyboardBuilder()
        kb.button(text="Получить реквизиты", callback_data="get_details")
        kb.button(text="Отменить", callback_data="back")
        kb.adjust(1, 1)

        operator = await get_operator()

        confirmation_text = (
            "📋 Подтверждение заявки:\n\n"
            f"💵 Сумма к оплате: <b>{rub_amount:,.2f} RUB</b>\n"
            f"💎 К получению: <b>{crypto_amount:.8f} {currency}</b>\n"
            f"📊 Курс: <b>1 {currency} = {rate:,.2f} RUB</b>\n"
            f"📊 Комиссия: <b>{commission:.2f}%</b> (включена в курс)\n"
            f"📍 Адрес получения: <code>{address}</code>\n\n"
            "⚠️ <b>Внимание:</b> Нажимая кнопку \"Получить реквизиты\", вы обязуетесь оплатить заявку в течение 15 минут. "
            "Вы не сможете отменить текущую заявку или создать новую до истечения времени оплаты.\n\n"
            "▪️▪️▪️▪️▪️▪️▪️▪️▪️▪️▪️▪️▪️▪️\n"
            f"🔆 Если возникли трудности, обратитесь к оператору: 👨‍💻 @{operator}"
        )

        await message.answer(confirmation_text, reply_markup=kb.as_markup())
    except Exception as error:
        print(f"Ошибка в process_address: {error}")
        await message.answer("❌ Произошла ошибка. Попробуйте еще раз.")


@router.callback_query(F.data == "get_details")
async def send_payment_details(callback: types.CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        currency = data["currency"]
        crypto_amount = data["crypto_amount"]
        rub_amount = data["rub_amount"]
        address = data["address"]

        request_number = random.randint(1000000, 9999999)

        kb = InlineKeyboardBuilder()
        kb.button(text="Оплатил", callback_data="paid")
        kb.button(text="Главная", callback_data="back")
        kb.adjust(1, 1)

        await state.clear()

        waiting_message = await callback.message.answer(
            "✅ Немного подождите, формируем реквизиты для оплаты..."
        )

        second = random.randint(5, 10)
        await asyncio.sleep(second)

        await waiting_message.delete()

        requisites = await get_requisites()
        bank = await get_bank()
        operator = await get_operator()

        payment_text = (
            "💰РЕКВИЗИТЫ ДЛЯ ОПЛАТЫ ⬇️\n\n"
            f"📎  № заявки  ➖ <b>{request_number}</b>\n"
            f"📎  Реквизиты ➖ <code>{requisites}</code>\n"
            f"📎  Банк  ➖ <code>{bank}</code>\n"
            f"📎  Сумма ➖ <b>{rub_amount:,.0f}</b> р.\n"
            f"📎  К получению ➖ <b>{crypto_amount:.8f} {currency}</b>\n\n"
            f"📍 Адрес для получения: <code>{address}</code>\n\n"
            f"После оплаты, пожалуйста, отправьте скриншот или фото подтверждения оплаты оператору @{operator} "
            "для ускорения обработки вашей заявки.\n\n"
            f"❤️Спасибо, что выбрали {BOT_NAME}!"
        )

        await callback.message.answer(payment_text, reply_markup=kb.as_markup())
        await callback.answer()
    except Exception as error:
        await callback.answer()
        print(f"Ошибка на [send_payment_details]: {error}")


@router.callback_query(F.data == "paid")
async def paid_handler(callback: types.CallbackQuery):
    try:
        operator = await get_operator()
        kb = InlineKeyboardBuilder()
        kb.button(text="Главная", callback_data="back")
        kb.adjust(1)

        await callback.message.answer(
            "♻️Ваша заявка на обмен принята♻️\n\n"
            "⏰Пожалуйста, ожидайте, в течение 2-х минут после поступления средств, "
            "на Ваш баланс будут зачислены монеты!\n\n"
            f"📸 Отправьте чек сюда: @{operator}",
            reply_markup=kb.as_markup(),
        )
        await callback.answer()
    except Exception as error:
        await callback.answer()
        print(f"Ошибка на [paid_handler]: {error}")
