import random
import asyncio
import aiohttp
from aiogram import Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from config import operator, operator2, operator3, ADMIN_IDS
from db.settings import (
    get_requisites, get_bank, get_payment_methods,
    get_requisites_mode, get_method_requisites, get_commission
)
from datetime import datetime

router = Router()


class Form(StatesGroup):
    waiting_for_amount = State()
    waiting_for_wallet = State()
    waiting_for_receipt = State()


CRYPTO_EXAMPLES = {
    "BTC": "0.01 или 0,01 или 5000",
    "XMR": "0.5 или 0,5 или 15000",
    "LTC": "0.5 или 0,5 или 3000"
}

MINIMUM_EXCHANGE_AMOUNT_RUB = 1500


async def get_usd_rub_rate() -> float:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://www.cbr-xml-daily.ru/daily_json.js",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    text = await response.text()
                    import json
                    data = json.loads(text)
                    usd_rate = data["Valute"]["USD"]["Value"]
                    return float(usd_rate)
    except Exception as e:
        print(f"CBR USD/RUB ошибка: {e}")
    return 90.0


async def get_crypto_price_usd(crypto_type: str) -> float:
    try:
        async with aiohttp.ClientSession() as session:
            if crypto_type == "XMR":
                url = "https://min-api.cryptocompare.com/data/price?fsym=XMR&tsyms=USD"
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        return float(data.get("USD", 0))
            else:
                symbol = f"{crypto_type}USDT"
                url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        return float(data.get("price", 0))
    except Exception as e:
        print(f'Exception caught: {e}')

    defaults = {"BTC": 68000.0, "XMR": 160.0, "LTC": 70.0}
    return defaults.get(crypto_type, 0)


async def get_crypto_rates(crypto_type: str) -> tuple:
    usd_price = await get_crypto_price_usd(crypto_type)
    rub_rate = await get_usd_rub_rate()
    final_rub_price = usd_price * rub_rate
    return usd_price, final_rub_price


@router.callback_query(F.data.startswith("buy_"))
async def buy_crypto_handler(callback: types.CallbackQuery, state: FSMContext):
    crypto_type = callback.data.split("_")[1].upper()

    await state.update_data(crypto_type=crypto_type)
    await state.set_state(Form.waiting_for_amount)

    examples = CRYPTO_EXAMPLES.get(crypto_type, "0.01 или 0,01 или 1000")

    text = (
        f"<b>Покупка {crypto_type}</b>\n\n"
        f"Укажите сумму в {crypto_type} или RUB:\n\n"
        f"Пример: <code>{examples}</code>\n\n"
        f"<b>Минимальная сумма обмена: {MINIMUM_EXCHANGE_AMOUNT_RUB} руб.</b>"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Отменить", callback_data="back")
    kb.adjust(1)

    await callback.message.delete()
    msg = await callback.message.answer(text, reply_markup=kb.as_markup())
    await state.update_data(request_message_id=msg.message_id)
    await callback.answer()


@router.message(Form.waiting_for_amount)
async def process_amount(message: Message, state: FSMContext):
    data = await state.get_data()
    crypto_type = data['crypto_type']
    amount = message.text.strip().replace(' ', '').replace(',', '.')

    try:
        amount_float = float(amount)
    except ValueError:
        await message.answer("❌ Неверный формат суммы. Пожалуйста, укажите число.")
        return

    rate_usd, rate_rub = await get_crypto_rates(crypto_type)
    commission = await get_commission()

    minimum_crypto = MINIMUM_EXCHANGE_AMOUNT_RUB / rate_rub

    try:
        if crypto_type == "BTC":
            threshold = 1
        else:
            threshold = 10

        if amount_float <= threshold:
            crypto_amount = amount_float
            amount_rub = crypto_amount * rate_rub

            if crypto_amount < minimum_crypto:
                if crypto_type == "BTC":
                    await message.answer(
                        f"❌ Минимальная сумма обмена: {MINIMUM_EXCHANGE_AMOUNT_RUB} руб. ({minimum_crypto:.6f} {crypto_type})")
                else:
                    await message.answer(
                        f"❌ Минимальная сумма обмена: {MINIMUM_EXCHANGE_AMOUNT_RUB} руб. ({minimum_crypto:.4f} {crypto_type})")
                return
        else:
            amount_rub = amount_float
            crypto_amount = amount_rub / rate_rub

            if amount_rub < MINIMUM_EXCHANGE_AMOUNT_RUB:
                if crypto_type == "BTC":
                    await message.answer(
                        f"❌ Минимальная сумма обмена: {MINIMUM_EXCHANGE_AMOUNT_RUB} руб. ({minimum_crypto:.6f} {crypto_type})")
                else:
                    await message.answer(
                        f"❌ Минимальная сумма обмена: {MINIMUM_EXCHANGE_AMOUNT_RUB} руб. ({minimum_crypto:.4f} {crypto_type})")
                return

        total_to_pay = round(amount_rub * (1 + commission / 100))
        formatted_crypto = "{:.8f}".format(crypto_amount).rstrip('0').rstrip('.')
        formatted_rub = "{:,.0f}".format(total_to_pay).replace(',', ' ')

        await state.update_data(crypto_amount=formatted_crypto, total_to_pay=total_to_pay)

        text = (
            f"Средний рыночный курс {crypto_type}: ${rate_usd:,.2f}, {await get_usd_rub_rate():,.2f} руб.\n\n"
            f"Вы получите: <b>{formatted_crypto} {crypto_type}</b>\n"
            f"Ваш внутренний баланс кошелька: <b>0 руб.</b>\n\n"
            f"Для продолжения выберите <b>Способ оплаты:</b>\n\n"
            "🔥Для получения скидки <b>20%</b> совершите еще <b>5 обменов.</b>🔥"
        )

        kb = InlineKeyboardBuilder()

        payment_methods = await get_payment_methods()
        for i, method in enumerate(payment_methods):
            kb.button(text=f"{method['name']} ({formatted_rub} руб.)",
                      callback_data=f"pay_method_{i}_{crypto_type}_{total_to_pay}")

        kb.button(text="🚫 Отмена", callback_data="back")
        kb.adjust(1)

        await message.answer(text, reply_markup=kb.as_markup())

    except Exception as e:
        print(f"❌ Ошибка: {str(e)}")


@router.callback_query(F.data.startswith("pay_method_"))
async def payment_method_handler(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    method_index = int(parts[2])
    crypto_type = parts[3]
    total_to_pay = parts[4]

    payment_methods = await get_payment_methods()
    selected_method = payment_methods[method_index]['name'] if method_index < len(payment_methods) else "Неизвестный"

    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Отменить", callback_data="back")
    kb.adjust(1)

    await state.update_data(
        payment_method=selected_method,
        crypto_type=crypto_type,
        total_to_pay=total_to_pay,
        method_index=method_index
    )
    await state.set_state(Form.waiting_for_wallet)

    await callback.message.delete()
    msg = await callback.message.answer(
        f"<b>Скопируйте и отправьте боту свой кошелек {crypto_type}</b>",
        reply_markup=kb.as_markup()
    )
    await state.update_data(wallet_request_message_id=msg.message_id)
    await callback.answer()


def generate_deal_id() -> str:
    now = datetime.now()
    return f"{now.strftime('%d%m%H%M')}{random.randint(100, 999)}"


def generate_deal_text(total_to_pay: int, wallet: str) -> tuple:
    deal_id = generate_deal_id()
    formatted_amount = f"{int(total_to_pay):,}".replace(',', ' ')

    text = (
        f"Время на оплату заказа №<code>{deal_id}</code> <b>15 минут!</b>\n\n"
        "<code>"
        f"‼️ Отправляйте деньги строго на банк, указанный в заявке, в противном случае ВЫ ПОТЕРЯЕТЕ ДЕНЬГИ ‼️\n"
        f"⚠️ Отправляйте четко ту сумму, которая указана в заявке, в противном случае ВЫ ПОТЕРЯЕТЕ ДЕНЬГИ ⚠️\n"
        f"⛔ Администрация может заморозить обмен и запросить дополнительную верификацию ⛔\n"
        "</code>\n"
        f"Итого к оплате: <b>{formatted_amount} руб.</b>\n\n"
        f"<b>ВНИМАТЕЛЬНО сверяйте адрес своего кошелька!</b>\n\n"
        f"После оплаты средства будут переведены на кошелек:\n"
        f"<code>{wallet}</code>\n\n"
        f"Если у вас есть вопрос, или возникли проблемы с оплатой, пишите поддержке:\n"
        f"@{operator} или @{operator2} или @{operator3}\n\n"
        f"<b>Вы согласны на обмен?</b>"
    )

    return text, deal_id


@router.message(Form.waiting_for_wallet)
async def process_wallet(message: Message, state: FSMContext):
    wallet = message.text.strip()
    await state.update_data(wallet=wallet)

    data = await state.get_data()

    if 'wallet_request_message_id' in data:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=data['wallet_request_message_id'])
        except Exception as e:
            print(f'Exception caught: {e}')

    text, deal_id = generate_deal_text(int(data['total_to_pay']), wallet)
    await state.update_data(deal_id=deal_id)

    kb = InlineKeyboardBuilder()
    kb.button(text="Списать с баланса 0 руб.", callback_data="write_balance")
    kb.button(text="❌ Отменить", callback_data="back")
    kb.button(text="✅ Да, согласен", callback_data=f"confirm_payment_{data['crypto_type']}_{data['total_to_pay']}")
    kb.adjust(1, 2)

    await message.delete()
    new_message = await message.answer(text, reply_markup=kb.as_markup())
    await state.update_data(wallet_request_message_id=new_message.message_id)


@router.callback_query(lambda c: c.data == 'write_balance')
async def handle_write_balance(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    text, _ = generate_deal_text(int(data['total_to_pay']), data.get('wallet', ''))

    kb = InlineKeyboardBuilder()
    kb.button(text="Списать с баланса 0 руб.", callback_data="write_balance")
    kb.button(text="❌ Отменить", callback_data="back")
    kb.button(text="✅ Да, согласен", callback_data=f"confirm_payment_{data['crypto_type']}_{data['total_to_pay']}")
    kb.adjust(1, 2)

    try:
        await callback.message.delete()
    except Exception as e:
        print(f'Exception caught: {e}')

    new_message = await callback.message.answer(text, reply_markup=kb.as_markup())
    await state.update_data(wallet_request_message_id=new_message.message_id)
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_payment_"))
async def confirm_payment_handler(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()

    if data.get('payment_confirmed') == callback.message.message_id:
        await callback.answer("❌ Кнопка уже нажата!", show_alert=True)
        return

    await state.update_data(payment_confirmed=callback.message.message_id)

    search_msg = await callback.message.answer(
        "⏳ Ищем подходящие реквизиты. Поиск обычно занимает от 1 до 30 секунд...")
    await state.update_data(requisites_message_id=search_msg.message_id)

    await asyncio.sleep(random.uniform(2, 7))

    mode = await get_requisites_mode()
    method_index = data.get('method_index', 0)

    if mode == 1:
        requisites, bank_name = await get_method_requisites(method_index)
    else:
        requisites = await get_requisites()
        bank_name = await get_bank()

    amount = int(callback.data.split('_')[3])
    formatted_amount = f"{amount:,}".replace(',', ' ')

    payment_text = (
        f"<b>Реквизиты для оплаты:</b>\n\n"
        f"<code>{requisites}</code>\n\n"
        f"Банк: {bank_name}\n\n"
        f"Сумма к оплате: <b>{formatted_amount} руб.</b>"
    )

    await search_msg.edit_text(payment_text)
    await callback.answer()

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Я оплатил", callback_data="confirm_paid")
    kb.button(text="🚫 Отменить текущий заказ", callback_data="cancel_order")
    kb.adjust(1)

    await callback.message.answer("Подтвердить оплату или отменить заказ:", reply_markup=kb.as_markup())


@router.callback_query(F.data == "confirm_paid")
async def handle_confirm_paid(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.message.delete()
    except:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception as e:
            print(f'Exception caught: {e}')

    await state.set_state(Form.waiting_for_receipt)
    await callback.message.answer(
        "Если вы оплатили, то можете отправить боту чек в формате PDF или скриншот.\n"
        "Это ускорит подтверждение платежа!"
    )
    await callback.answer()


@router.callback_query(F.data == "cancel_order")
async def handle_cancel_order(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    for key in ["request_message_id", "wallet_request_message_id", "payment_confirmed", "requisites_message_id"]:
        if key in data:
            try:
                await callback.bot.delete_message(chat_id=callback.message.chat.id, message_id=data[key])
            except Exception as e:
                print(f'Exception caught: {e}')

    try:
        await callback.message.delete()
    except Exception as e:
        print(f'Exception caught: {e}')

    deal_id = data.get('deal_id', generate_deal_id())
    await state.clear()

    await callback.message.answer(
        f"Ваш заказ №<code>{deal_id}</code> отменен!",
        reply_markup=InlineKeyboardBuilder().button(text="Главное меню", callback_data="back").as_markup()
    )
    await callback.answer()


@router.message(Form.waiting_for_receipt)
async def process_receipt(message: Message, state: FSMContext):
    data = await state.get_data()
    deal_id = data.get("deal_id", generate_deal_id())

    if message.document:
        for admin_id in ADMIN_IDS:
            try:
                await message.bot.send_document(
                    chat_id=admin_id,
                    document=message.document.file_id,
                    caption=(
                        f"📄 Чек по заказу №{deal_id}\n"
                        f"От пользователя @{message.from_user.username or message.from_user.id}\n"
                        f"Файл: {message.document.file_name}"
                    )
                )
            except Exception as e:
                print(f"Ошибка отправки документа админу {admin_id}: {e}")

        kb = InlineKeyboardBuilder()
        kb.button(text="🏠 Главное меню", callback_data="back")
        await message.answer("✅ Чек принят, ожидайте зачисление в течении 20 минут!", reply_markup=kb.as_markup())
        await state.clear()
        return

    if message.photo:
        photo = message.photo[-1]
        for admin_id in ADMIN_IDS:
            try:
                await message.bot.send_photo(
                    chat_id=admin_id,
                    photo=photo.file_id,
                    caption=(
                        f"🖼 Скрин по заказу №{deal_id}\n"
                        f"От пользователя @{message.from_user.username or message.from_user.id}"
                    )
                )
            except Exception as e:
                print(f"Ошибка отправки фото админу {admin_id}: {e}")

        kb = InlineKeyboardBuilder()
        kb.button(text="Главное меню", callback_data="back")
        await message.answer("✅ Чек принят, ожидайте зачисление в течении 20 минут!", reply_markup=kb.as_markup())
        await state.clear()
        return

    await message.answer("❌ Пожалуйста, отправьте чек в виде документа или изображения.")