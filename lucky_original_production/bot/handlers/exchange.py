import os
import asyncio
import html
import re
import random
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from core.models import User, Order, OrderType, OrderStatus, Rate, FileCache, Setting
from core.config import Config
from bot.keyboards.main_kb import (
    get_currencies_kb, get_buy_methods_kb, get_amount_type_kb
)
from bot.keyboards.banks_kb import get_banks_kb

router = Router()

EXCHANGE_CACHE: dict = {}

class ExchangeSG(StatesGroup):
    choosing_currency = State()
    choosing_method = State()
    choosing_bank = State()
    choosing_amount_type = State()
    entering_amount = State()
    entering_wallet = State()
    confirming = State()
    entering_promo = State()
    entering_phone = State()
    entering_fio = State()
    uploading_proof = State()

ANIMATIONS = {
    "buy": os.path.join(Config.BASE_DIR, "assets", "animation_buy.mp4"),
    "sell": os.path.join(Config.BASE_DIR, "assets", "animation_sell.mp4"),
    "start": os.path.join(Config.BASE_DIR, "assets", "animation_start.mp4"),
}

async def get_cached_file_id(session: AsyncSession, key: str):
    result = await session.execute(select(FileCache).where(FileCache.key == key))
    cached = result.scalar_one_or_none()
    return cached.file_id if cached else None

async def save_file_id(session: AsyncSession, key: str, file_id: str):
    session.add(FileCache(key=key, file_id=file_id))
    await session.commit()

async def get_app_setting(session: AsyncSession, key: str, default: str):
    result = await session.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    return setting.value if setting else default

COINGECKO_IDS = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "ltc": "litecoin",
    "usdt": "tether",
    "usdc": "usd-coin",
}

async def fetch_coingecko_rate(ticker: str) -> float | None:
    coin_id = COINGECKO_IDS.get(ticker.lower())
    if not coin_id:
        return None
    url = f"{Config.COINGECKO_API_URL}/simple/price"
    params = {"ids": coin_id, "vs_currencies": "rub"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            return data.get(coin_id, {}).get("rub")
    except Exception as e:
        logging.warning(f"CoinGecko API error for {ticker}: {e}")
        return None

async def get_crypto_rate_rub(session: AsyncSession, ticker: str, order_type: str = "buy") -> float | None:
    # Try CoinGecko first
    rate = await fetch_coingecko_rate(ticker)
    if rate:
        return rate
    # Fallback to DB
    result = await session.execute(select(Rate).where(Rate.currency == ticker))
    rate_obj = result.scalar_one_or_none()
    if not rate_obj:
        return None
    return rate_obj.buy_rate if order_type == "buy" else rate_obj.sell_rate

async def send_exchange_animation(message: Message, action: str, caption: str, reply_markup: InlineKeyboardMarkup, session: AsyncSession):
    cache_key = f"{action}_gif"
    file_id = await get_cached_file_id(session, cache_key)
    file_to_send = file_id if file_id else FSInputFile(ANIMATIONS[action])

    try:
        sent_msg = await message.answer_animation(animation=file_to_send, caption=caption or " ", reply_markup=reply_markup, parse_mode="HTML")
        if not file_id and hasattr(sent_msg, 'animation') and sent_msg.animation:
            await save_file_id(session, cache_key, sent_msg.animation.file_id)
    except Exception:
        if file_id:
            logging.warning(f"Cached file_id for {cache_key} invalid, retrying with file...")
            file_to_send = FSInputFile(ANIMATIONS[action])
            sent_msg = await message.answer_animation(animation=file_to_send, caption=caption or " ", reply_markup=reply_markup, parse_mode="HTML")
            if hasattr(sent_msg, 'animation') and sent_msg.animation:
                await session.execute(update(FileCache).where(FileCache.key == cache_key).values(file_id=sent_msg.animation.file_id))
                await session.commit()

@router.callback_query(F.data == "buy_main")
async def cmd_buy_inline(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    await state.clear()
    await state.set_state(ExchangeSG.choosing_currency)
    await state.update_data(order_type="buy")
    if callback.message:
        await send_exchange_animation(callback.message, "buy", "<b>Выберите криптовалюту для покупки</b>", get_currencies_kb("buy"), session)
    await callback.answer()

@router.callback_query(F.data == "sell_main")
async def cmd_sell_inline(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    await state.clear()
    await state.set_state(ExchangeSG.choosing_currency)
    await state.update_data(order_type="sell")
    if callback.message:
        await send_exchange_animation(callback.message, "sell", "<b>Выберите криптовалюту для продажи:</b>", get_currencies_kb("sell"), session)
    await callback.answer()

@router.callback_query(ExchangeSG.choosing_currency, F.data.startswith(("buy_", "sell_")))
async def process_currency(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    if not callback.data: return
    data = callback.data.split("_")
    action, currency = data[0], data[1]
    await state.update_data(currency=currency)

    if action == "sell":
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="📲 СБП", callback_data="method_SBP"))
        builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main"))
        if callback.message:
            await callback.message.answer(f"Продажа {currency}\n\nВыберите способ получения средств:", reply_markup=builder.as_markup())
        await state.set_state(ExchangeSG.choosing_method)
    else:
        if callback.message:
            await callback.message.answer(f"Выберите метод оплаты для покупки {currency}:", reply_markup=get_buy_methods_kb())
        await state.set_state(ExchangeSG.choosing_method)
    await callback.answer()

async def prompt_amount_input(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    currency = data.get('currency')
    if not currency: return

    if data.get('order_type') == "sell":
        await state.update_data(amt_type="token")
        rate = await get_crypto_rate_rub(session, currency, "sell")
        if rate is None:
            await message.answer("⚠️ Сервис временно недоступен: не удалось получить курс валюты.")
            return
        await state.update_data(rate=rate)
        min_token = 5000 / rate
        text = f"<b>Продажа {currency}</b>\n\nТекущий курс: 1 {currency} = {rate:,.3f} ₽\n\n⚠️ <b>Минимальная сумма к получению: {min_token:.8f} {currency}</b>\n\nВведите кол-во {currency} для продажи:"
        await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]]), parse_mode="HTML")
        await state.set_state(ExchangeSG.entering_amount)
    else:
        await message.answer("Выберите способ ввода суммы:", reply_markup=get_amount_type_kb())
        await state.set_state(ExchangeSG.choosing_amount_type)

@router.callback_query(ExchangeSG.choosing_method, F.data.startswith("method_"))
async def process_method_choice(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    if not callback.data or not callback.message: return
    method = callback.data.split("_")[1]
    await state.update_data(method=method)
    if method == "SBP":
        await callback.message.answer("Выберите ваш банк для получения по СБП:", reply_markup=get_banks_kb(0))
        await state.set_state(ExchangeSG.choosing_bank)
    else:
        await prompt_amount_input(callback.message, state, session)
    await callback.answer()

@router.callback_query(ExchangeSG.choosing_bank, F.data.startswith("banks_page_"))
async def process_banks_pagination(callback: CallbackQuery, state: FSMContext):
    if not callback.data or not callback.message: return
    page = int(callback.data.split("_")[2])
    await callback.message.edit_reply_markup(reply_markup=get_banks_kb(page))
    await callback.answer()

@router.callback_query(ExchangeSG.choosing_bank, F.data.startswith("bank_"))
async def process_bank_choice(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    if not callback.data or not callback.message: return
    await state.update_data(bank_name=callback.data.replace("bank_", ""))
    await prompt_amount_input(callback.message, state, session)
    await callback.answer()

@router.callback_query(ExchangeSG.choosing_amount_type, F.data.startswith("amt_"))
async def process_amount_type(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    if not callback.data or not callback.message: return
    amt_type = callback.data.split("_")[1]
    await state.update_data(amt_type=amt_type)
    data = await state.get_data()
    rate = await get_crypto_rate_rub(session, data['currency'], data['order_type'])
    if rate is None:
        await callback.message.answer("⚠️ Сервис временно недоступен: не удалось получить курс валюты.")
        return
    await state.update_data(rate=rate)
    prefix = "Покупка" if data['order_type'] == "buy" else "Продажа"
    min_rub = 1000 if data['order_type'] == "buy" else 5000
    if amt_type == "rub":
        min_text = f"{min_rub:,.0f} ₽"
    else:
        min_text = f"{min_rub / rate:.8f} {data['currency']}"
    text = f"<b>{prefix} {data['currency']}</b>\n\nВведите сумму в {'рублях' if amt_type == 'rub' else 'токенах'}:\n\nМинимальная сумма: {min_text}"
    await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]]), parse_mode="HTML")
    await state.set_state(ExchangeSG.entering_amount)
    await callback.answer()

@router.message(ExchangeSG.entering_amount)
async def process_exchange_amount(message: Message, state: FSMContext, session: AsyncSession):
    if not message.text: return
    try:
        amount = float(message.text.replace(",", ".").replace(" ", ""))
        data = await state.get_data()
        if 'rate' not in data:
             await message.answer("⚠️ Ошибка сессии. Пожалуйста, начните заново.")
             return
        if data['order_type'] == "buy" and data.get('amt_type') == "token":
            total_rub = (amount * data['rate'] + Config.NETWORK_FEE) / (1 - Config.COMMISSION_BUY / 100)
        else:
            total_rub = amount if data.get('amt_type') == "rub" else amount * data['rate']
        min_amount = 5000 if data['order_type'] == "sell" else 1000
        if total_rub < min_amount:
            await message.answer(f"⚠️ Минимальная сумма: {min_amount:,.0f} ₽")
            return
        await state.update_data(amount=amount, total_rub=total_rub)
        if data['order_type'] == "buy":
            await message.answer("Введите адрес вашего кошелька для получения:")
            await state.set_state(ExchangeSG.entering_wallet)
        else:
            await message.answer("Введите номер телефона для получения по СБП (11 цифр):\n\nПример: <code>79001234567</code>", parse_mode="HTML")
            await state.set_state(ExchangeSG.entering_phone)
    except ValueError:
        await message.answer("❌ Ошибка ввода. Введите число.")

@router.message(ExchangeSG.entering_wallet)
async def process_buy_wallet(message: Message, state: FSMContext):
    if not message.text: return
    wallet = html.escape(message.text.strip())
    if len(wallet) < 10 or not re.match(r"^[a-zA-Z0-9]+$", wallet):
        await message.answer("⚠️ Некорректный адрес кошелька. Введите корректный адрес:")
        return
    await state.update_data(wallet=wallet)
    data = await state.get_data()
    commission_svc = data['total_rub'] * (Config.COMMISSION_BUY / 100)
    to_receive = (data['total_rub'] - commission_svc - Config.NETWORK_FEE) / data['rate']
    await state.update_data(amount_out=to_receive)
    text = f"☘️ <b>Подтверждение заказа:</b>\n\n☘️ <b>Сумма:</b> {data['total_rub']:,.0f} RUB\n☘️ <b>Курс:</b> 1 {data['currency']} = {data['rate']:,.2f} RUB\n☘️ <b>Комиссия сервиса:</b> {Config.COMMISSION_BUY:.0f}% ({commission_svc:,.0f} RUB)\n☘️ <b>Комиссия сети:</b> {Config.NETWORK_FEE:.0f} RUB\n☘️ <b>Получите:</b> {to_receive:.8f} {data['currency']}\n☘️ <b>Метод:</b> {data['method']}\n☘️ <b>Кошелек:</b> <code>{wallet}</code>\n\n☘️ <b>Итого к оплате:</b> {data['total_rub']:,.0f} RUB"
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Подтвердить", callback_data="buy_confirm"))
    builder.row(InlineKeyboardButton(text="Отменить", callback_data="back_to_main"))
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await state.set_state(ExchangeSG.confirming)

@router.message(ExchangeSG.entering_phone)
async def process_sell_phone(message: Message, state: FSMContext):
    if not message.text: return
    phone = message.text.strip().replace("+", "").replace(" ", "")
    if not (phone.isdigit() and len(phone) == 11):
        await message.answer("❌ Введите 11 цифр телефона (например: 79001234567):")
        return
    await state.update_data(phone=phone)
    await message.answer("Введите ФИО владельца счета/карты (рекомендованно):")
    await state.set_state(ExchangeSG.entering_fio)

@router.message(ExchangeSG.entering_fio)
async def process_sell_fio(message: Message, state: FSMContext):
    if not message.text: return
    fio = html.escape(message.text.strip())
    if len(fio) < 5:
        await message.answer("❌ Слишком короткое ФИО.")
        return
    await state.update_data(fio=fio)
    data = await state.get_data()
    commission = data['total_rub'] * (Config.COMMISSION_BUY / 100)
    to_receive = data['total_rub'] - commission
    await state.update_data(amount_out=to_receive)
    text = f"<b>Подтверждение заказа</b>\n\n<b>Детали заявки:</b>\nОтдаете: {data['amount']} {data['currency']}\nКурс: 1 {data['currency']} = {data['rate']:,.3f} ₽\nКомиссия сервиса: {Config.COMMISSION_BUY:.0f}% ({commission:,.0f} ₽)\nК получению: <b>{to_receive:,.0f} ₽</b>\n\n<b>Реквизиты для выплаты по СБП:</b>\nТелефон: <code>{data['phone']}</code>\nПолучатель: {fio}\nБанк: {data.get('bank_name', 'Кибит')}\n\n⚠️ <b>После подтверждения:</b>\n1. Вы получите адрес для отправки {data['currency']}\n2. Отправьте <b>точную сумму</b> на указанный адрес\n3. После получения криптовалюты средства будут отправленны\nна реквизиты в течение 1 часа"
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Подтвердить", callback_data="sell_confirm"))
    builder.row(InlineKeyboardButton(text="Отменить", callback_data="back_to_main"))
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await state.set_state(ExchangeSG.confirming)

@router.callback_query(ExchangeSG.confirming, F.data.endswith("_confirm"))
async def process_final(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    res = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
    user = res.scalar_one()
    new_order = Order(
        user_id=user.id, type=OrderType.BUY if data['order_type'] == "buy" else OrderType.SELL,
        status=OrderStatus.PENDING, amount_in=data['amount'] if data['order_type'] == "sell" else data['total_rub'],
        currency_in=data['currency'] if data['order_type'] == "sell" else "RUB",
        amount_out=data['amount_out'], currency_out="RUB" if data['order_type'] == "sell" else data['currency'],
        payment_method=data['method'], bank_name=data.get('bank_name'), requisites_phone=data.get('phone'),
        requisites_fio=data.get('fio'), wallet_address=data.get('wallet')
    )
    session.add(new_order)
    await session.commit()
    if callback.message:
        wait_msg = await callback.message.answer("⏳ Идёт поиск реквизитов, пожалуйста подождите...")
        await asyncio.sleep(10)
        await wait_msg.delete()
    order_num = f"{callback.from_user.id}{random.randint(1000, 9999)}"
    order_id_str = f"LXY-{new_order.id}"
    if data['order_type'] == "sell":
        address = await get_app_setting(session, f"wallet_{data['currency']}", "bc1qwtep566frhslr3rvzf2an6k4ykhkgwzy4nlc24")
        text = f"☘️ <b>Заявка №{order_num} успешно создана!</b>\n\n📎 <b>Адрес для перевода {data['currency']}:</b>\n\n<code>{address}</code>\n\n📎 <b>Сумма к отправке:</b> <code>{data['amount']} {data['currency']}</code>\n📎 <b>Курс:</b> 1 {data['currency']} = {data['rate']:,.2f} ₽\n\n📎 <b>Реквизиты для получения (СБП):</b>\n      Телефон: <code>{data['phone']}</code>\n      Получатель: {data['fio']}\n      Банк: {data.get('bank_name', 'Кибит')}\n\n💳 <b>Сумма к получению:</b> <u>{data['amount_out']:,.0f} ₽</u>"
    else:
        req_key = "requisites_global"
        bank_key = "requisites_bank"
        requisites = await get_app_setting(session, req_key, "2200151668725984")
        bank_name = await get_app_setting(session, bank_key, "Альфа Банк")

        text = f"""☘️ <b>Заявка №{order_num} успешно создана!</b>

📎 <b>Адрес зачисления:</b>
<code>{data.get('wallet')}</code>

📎 <b>Вы получаете:</b> <code>{data['amount_out']:.8f}</code> {data['currency']}

📎 <b>Реквизиты для оплаты:</b>

<code>{requisites}</code> || {bank_name}

💳 <b>Сумма к оплате:</b> <code>{data['total_rub']:,.0f}</code> ₽

✅ <b>На оплату 15 минут, после оплаты необходимо нажать на кнопку "ОПЛАТИЛ"</b>"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Оплатил", callback_data=f"paid_{order_id_str}"))
    builder.row(InlineKeyboardButton(text="Отменить заявку", callback_data="back_to_main"))
    if callback.message:
        await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await state.clear()
    await callback.answer()

@router.callback_query(F.data.startswith("paid_"))
async def process_paid_button(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ExchangeSG.uploading_proof)
    await state.update_data(current_order_id=callback.data.split("_")[1])
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Назад", callback_data="back_to_main"))
    if callback.message:
        await callback.message.answer("☘️ Отправьте скрин перевода, либо чек оплаты.", reply_markup=builder.as_markup())
    await callback.answer()

@router.message(ExchangeSG.uploading_proof, F.photo | F.document)
async def process_proof_upload(message: Message, state: FSMContext, session: AsyncSession): 
    data = await state.get_data()
    order_id = data.get('current_order_id', 'Unknown')
    try:
        admin_text = f"🧾 <b>Новый чек оплаты!</b>\nOrder ID: {order_id}\nUser: {message.from_user.full_name if message.from_user else 'User'}"
        await message.forward(chat_id=Config.ADMIN_ID)
        await message.bot.send_message(chat_id=Config.ADMIN_ID, text=admin_text, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Admin notify error: {e}")
    await message.answer("✅ <b>Ожидайте зачисление после проверки платежа, 15-30 минут !</b>", parse_mode="HTML")
    await state.clear()