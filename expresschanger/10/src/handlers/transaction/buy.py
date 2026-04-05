import asyncio
import os
import random
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from src.utils.rates import get_btc_rub_rate, get_ltc_rub_rate, get_xmr_rub_rate
from src.keyboards.transaction import buy_button_operation, button_buy_back, vip_payment_button, order_buttons, payment_details_buttons, requisites_action_buttons
from src.states.transaction import BuyCryptoState
from src.texts.transaction import TransactionTexts
from src.utils.group import send_message_to_channel
from src.utils.manager import manager
from src.utils.orders import create_order
from dotenv import load_dotenv

load_dotenv()
OPERATOR_USERNAME = os.getenv("OPERATOR_USERNAME", "@expresschanger_support_bot")

buy_router = Router()
texts = TransactionTexts()

MIN_RUB = 1500


@buy_router.callback_query(F.data.startswith('buy_'))
async def callback_start_button(callback: CallbackQuery, state: FSMContext) -> None:
    currency = callback.data.replace("buy_", "")
    await manager.delete_message(callback.message.chat.id)
    new_message = await callback.message.answer(texts.get("buy_currency", currency=currency.upper()),
                                                reply_markup=buy_button_operation(crypto=False, currency=currency))
    await manager.set_message(callback.message.chat.id, new_message)
    await state.update_data(currency=currency)
    await state.update_data(payment_method="crypto")
    await state.set_state(BuyCryptoState.value)


@buy_router.callback_query(F.data == 'operation_buy_ru', BuyCryptoState.value)
async def callback_buy_button(callback: CallbackQuery, state: FSMContext) -> None:
    await manager.delete_message(callback.message.chat.id)
    data = await state.get_data()
    currency = data.get("currency")
    await state.update_data(payment_method="rub")
    await state.set_state(BuyCryptoState.value)
    new_message = await callback.message.answer(texts.get("buy_operation_ru"),
                                                reply_markup=buy_button_operation(crypto=True, currency=currency))
    await manager.set_message(callback.message.chat.id, new_message)


@buy_router.callback_query(F.data == 'operation_buy_crypto', BuyCryptoState.value)
async def callback_buy_button(callback: CallbackQuery, state: FSMContext) -> None:
    await manager.delete_message(callback.message.chat.id)
    data = await state.get_data()
    currency = data.get("currency")
    await state.update_data(payment_method="crypto")
    await state.set_state(BuyCryptoState.value)
    new_message = await callback.message.answer(texts.get("buy_currency", currency=currency.upper()),
                                                reply_markup=buy_button_operation(crypto=False, currency=currency))
    await manager.set_message(callback.message.chat.id, new_message)


@buy_router.message(BuyCryptoState.value, ~F.text.startswith("/"))
async def process_entered_value(message: Message, state: FSMContext):
    from src.handlers.user.promocodes import user_promo_codes
    data = await state.get_data()
    payment_method = data.get("payment_method")
    currency = data.get("currency")
    promo_codes_list = user_promo_codes.get(message.from_user.id, [])
    try:
        value = float(message.text.replace(",", "."))
        await state.update_data(value=value)
        total_sum = 0
        promo_discounts = {"WELCOME": 300, "EXPRESS": 1000}
        applied_promos = [p for p in promo_codes_list if p in promo_discounts]
        if applied_promos:
            await state.update_data(promo_codes=applied_promos)
        promo_text = "🎁 Применён промокод <b>WELCOME (300₽)</b>\n💎 Применён промокод <b>EXPRESS (1000₽)</b>\n"
        from src.db.settings import get_commission
        commission = await get_commission()
        if payment_method == "rub":
            if currency == "ltc":
                rate = await get_ltc_rub_rate()
                total_sum = value / rate
            elif currency == "btc":
                rate = await get_btc_rub_rate()
                total_sum = value / rate
            elif currency == "xmr":
                rate = await get_xmr_rub_rate()
                total_sum = value / rate

            total_sum_rounded = round(total_sum, 8)
            if value < MIN_RUB:
                prompt = texts.get("buy_operation_ru")
                await message.answer(texts.get("error_min_rub", min_rub=MIN_RUB) + prompt)
                return
            new_message = await message.answer(
                texts.get("buy_success_rub", value=int(value), currency=currency.upper(), total_sum=total_sum_rounded, promo_text=promo_text),
                reply_markup=button_buy_back())

        else:
            if currency == "ltc":
                rate = await get_ltc_rub_rate()
                total_sum = rate * value
            elif currency == "btc":
                rate = await get_btc_rub_rate()
                total_sum = rate * value
            elif currency == "xmr":
                rate = await get_xmr_rub_rate()
                total_sum = rate * value
            rub_amount = total_sum
            if total_sum < MIN_RUB:
                prompt = texts.get("buy_currency", currency=currency.upper())
                await message.answer(texts.get("error_min_rub", min_rub=MIN_RUB) + prompt)
                return
            sum_to_pay = round(rub_amount * (1 + commission / 100))
            new_message = await message.answer(
                texts.get("buy_success_crypto", value=value, currency=currency.upper(), total_sum=sum_to_pay, promo_text=promo_text),
                reply_markup=button_buy_back())
        total_sum = round(total_sum, 6)

        await state.update_data(total_sum=total_sum)
        await state.set_state(BuyCryptoState.cosh)
        await manager.set_message(message.chat.id, new_message)
    except ValueError:
        error_text = texts.get("error_buy")
        if payment_method == "rub":
            prompt_text = texts.get("buy_operation_ru")
        else:
            currency = data.get("currency", "btc")
            prompt_text = texts.get("buy_currency", currency=currency.upper())

        new_message = await message.answer(error_text + prompt_text)
        await manager.set_message(message.chat.id, new_message)


@buy_router.message(BuyCryptoState.cosh, ~F.text.startswith("/"))
async def process_entered_cosh(message: Message, state: FSMContext):
    from src.handlers.user.promocodes import user_promo_codes
    data = await state.get_data()
    payment_method = data.get("payment_method")
    currency = data.get("currency")
    if not currency or not payment_method:
        await state.clear()
        return

    try:
        new_value = float((message.text or "").strip().replace(",", "."))
    except ValueError:
        new_value = None
    if new_value is not None:
        from src.db.settings import get_commission
        commission = await get_commission()
        await manager.delete_message(message.chat.id)
        await state.update_data(value=new_value)
        value = new_value
        total_sum = 0
        promo_text = "🎁 Применён промокод <b>WELCOME (300₽)</b>\n💎 Применён промокод <b>EXPRESS (1000₽)</b>\n"
        if payment_method == "rub":
            rub_amount = value
            if currency == "ltc":
                total_sum = value / await get_ltc_rub_rate()
            elif currency == "btc":
                total_sum = value / await get_btc_rub_rate()
            elif currency == "xmr":
                total_sum = value / await get_xmr_rub_rate()
            if value < MIN_RUB:
                await message.answer(texts.get("error_min_rub", min_rub=MIN_RUB) + texts.get("buy_operation_ru"))
                return
            total_sum_rounded = round(total_sum, 8)
            new_message = await message.answer(
                texts.get("buy_success_rub", value=int(value), currency=currency.upper(), total_sum=total_sum_rounded, promo_text=promo_text),
                reply_markup=button_buy_back())
        else:
            if currency == "ltc":
                total_sum = await get_ltc_rub_rate() * value
            elif currency == "btc":
                total_sum = await get_btc_rub_rate() * value
            elif currency == "xmr":
                total_sum = await get_xmr_rub_rate() * value
            rub_amount = total_sum
            if total_sum < MIN_RUB:
                await message.answer(texts.get("error_min_rub", min_rub=MIN_RUB) + texts.get("buy_currency", currency=currency.upper()))
                return
            sum_to_pay = round(rub_amount * (1 + commission / 100))
            new_message = await message.answer(
                texts.get("buy_success_crypto", value=value, currency=currency.upper(), total_sum=sum_to_pay, promo_text=promo_text),
                reply_markup=button_buy_back())
        await state.update_data(total_sum=round(total_sum, 6))
        await manager.set_message(message.chat.id, new_message)
        return

    value = data.get("value")
    total_sum = data.get("total_sum")
    if value is None or total_sum is None:
        await state.clear()
        return
    await manager.delete_message(message.chat.id)
    cosh = (message.text or "").strip()
    await state.update_data(cosh=cosh)
    await state.update_data(priority="normal")
    if payment_method == "rub":
        rub_amount = float(value)
    else:
        rub_amount = float(total_sum)
    from src.db.settings import get_commission
    commission = await get_commission()
    final_sum = round(rub_amount * (1 + commission / 100))
    await state.update_data(final_sum=final_sum)
    new_message = await message.answer(
        texts.get("buy_success_upload_rub",
                 cosh=cosh,
                 total_sum=final_sum,
                 vip_sum=final_sum,
                 vip_fee=300,
                 currency=currency.upper()),
        reply_markup=await vip_payment_button()
    )
    await manager.set_message(message.chat.id, new_message)
    await state.set_state(BuyCryptoState.awaiting_payment_method)


@buy_router.callback_query(F.data.startswith('payment_method_'))
async def callback_payment_method(callback: CallbackQuery, state: FSMContext) -> None:
    from src.db.settings import get_payment_methods, get_requisites_mode, get_method_requisites, get_requisites, get_bank, get_commission
    await callback.answer()
    method_index = int(callback.data.split("_")[2])
    data = await state.get_data()
    value = data.get("value")
    currency = data.get("currency")
    total_sum = data.get("total_sum")
    payment_method_type = data.get("payment_method")
    cosh = data.get("cosh")
    priority = data.get("priority", "normal")
    if payment_method_type == "rub":
        rub_amount = float(value)
    else:
        rub_amount = float(total_sum)
    commission = await get_commission()
    final_sum = round(rub_amount * (1 + commission / 100))
    await state.update_data(final_sum=final_sum)
    if payment_method_type == "rub":
        value_rub = value
        value_crypto = total_sum
        unit = "RUB"
    else:
        value_crypto = value
        value_rub = total_sum
        unit = currency.upper()
    
    currency_upper = currency.upper()
    if currency_upper == "BTC":
        currency_display = "BTC"
    elif currency_upper == "LTC":
        currency_display = "LTC"
    elif currency_upper == "XMR":
        currency_display = "XMR"
    else:
        currency_display = currency_upper
    
    methods = await get_payment_methods()
    if method_index >= len(methods):
        await callback.answer("❌ Способ оплаты не найден", show_alert=True)
        return
    
    method_name = methods[method_index]["name"]
    
    formatted_crypto = f"{value_crypto:.8f}".rstrip('0').rstrip('.')
    
    order_id = str(random.randint(100000, 999999))
    
    details_text = f"""<b>💼 Детали вашей сделки</b>

<b>💰 Сумма:</b> <u>{final_sum}</u> ₽
<b>🪙 Метод оплаты:</b> {method_name}
<b>📥 Адрес для зачисления:</b> <code>{cosh}</code>
<b>💰 Сумма зачисления:</b> {formatted_crypto} {currency_display}

⏳ Реквизиты будут отправлены в течение <b>10 минут</b>
⚡ После оплаты перевод будет отправлен в течение <b>5 минут</b>"""
    
    await manager.delete_message(callback.message.chat.id)
    new_message = await callback.message.answer(
        details_text,
        reply_markup=payment_details_buttons(order_id)
    )
    await manager.set_message(callback.message.chat.id, new_message)
    
    await state.update_data(order_id=order_id)
    await state.update_data(value_crypto=value_crypto)
    await state.update_data(value_rub=value_rub)
    await state.update_data(unit=unit)
    await state.update_data(payment_method_index=method_index)
    await state.update_data(method_name=method_name)
    await state.update_data(currency=currency)
    await state.update_data(cosh=cosh)
    await state.update_data(final_sum=final_sum)


@buy_router.callback_query(F.data.startswith('start_exchange_'))
async def callback_start_exchange(callback: CallbackQuery, state: FSMContext) -> None:
    from src.handlers.user.promocodes import user_promo_codes
    from src.db.settings import get_payment_methods
    order_id = callback.data.replace("start_exchange_", "")
    data = await state.get_data()
    
    currency = data.get("currency")
    value_crypto = data.get("value_crypto")
    value_rub = data.get("value_rub")
    unit = data.get("unit")
    priority = data.get("priority", "normal")
    final_sum = data.get("final_sum")
    payment_method_index = data.get("payment_method_index", 0)
    method_name = data.get("method_name", "")
    cosh = data.get("cosh")
    promo_codes_list = user_promo_codes.get(callback.from_user.id, [])
    
    if not method_name:
        methods = await get_payment_methods()
        if 0 <= payment_method_index < len(methods):
            method_name = methods[payment_method_index]["name"]
        else:
            method_name = "Неизвестный метод"
    
    if promo_codes_list:
        user_promo_codes.pop(callback.from_user.id, None)
    
    create_order(order_id, callback.message.chat.id, {
        "currency": currency,
        "value_crypto": value_crypto,
        "value_rub": value_rub,
        "unit": unit,
        "priority": priority,
        "final_sum": final_sum,
        "payment_method_index": payment_method_index,
        "method_name": method_name,
        "wallet": cosh,
        "promo_codes": promo_codes_list
    })
    
    expires_at = datetime.now() + timedelta(minutes=30)
    expires_str = expires_at.strftime("%H:%M %d.%m")
    
    currency_upper = currency.upper()
    if currency_upper == "BTC":
        currency_display = "BTC"
    elif currency_upper == "LTC":
        currency_display = "LTC"
    elif currency_upper == "XMR":
        currency_display = "XMR"
    else:
        currency_display = currency_upper
    
    crypto_amount = f"{value_crypto:.8f}".rstrip('0').rstrip('.')
    
    order_text = f"""<b>📄 Ваша заявка №{order_id}</b>
🕒 Действительна до {expires_str} (30 мин)

<b>💰 Сумма к оплате:</b> <u>{final_sum}</u> ₽
<b>🪙 Получаете:</b> {crypto_amount} {currency_display}
<b>🏦 Адрес зачисления:</b> <code>{cosh}</code>

⏳ Реквизиты формируются — это займёт немного времени.
📬 Как только они будут готовы, бот пришлёт уведомление автоматически.

🤝 Если нужна помощь — напишите оператору: {OPERATOR_USERNAME}"""
    
    warning_text = """<b>⚠️ Перед оплатой внимательно ознакомьтесь</b>

<b>🔸 Оплачивайте строго тем способом, который был выбран при создании заявки.</b>
Переводы другими методами не обрабатываются системой и не могут быть засчитаны.

<b>🔸 Система работает автоматически.</b>
Если указать неверную сумму, реквизиты или банк — платёж не будет определён и средства не смогут зачислиться.

💡 Пожалуйста, проверяйте все данные перед отправкой перевода — это поможет избежать задержек и ошибок."""
    
    await manager.delete_message(callback.message.chat.id)
    new_message = await callback.message.answer(
        order_text,
        reply_markup=order_buttons(order_id)
    )
    await manager.set_message(callback.message.chat.id, new_message)
    
    await callback.message.answer(warning_text)
    
    await asyncio.sleep(10)
    
    from src.db.settings import get_requisites_mode, get_method_requisites, get_requisites, get_bank
    
    mode = await get_requisites_mode()
    method_index = data.get("payment_method_index", 0)
    
    if mode == 1:
        requisites, bank_name = await get_method_requisites(method_index)
    else:
        requisites = await get_requisites()
        bank_name = await get_bank()
    
    if not requisites:
        await callback.message.answer("❌ Реквизиты для выбранного метода оплаты не настроены. Обратитесь к администратору.")
        await callback.answer()
        return
    
    card = requisites
    recipient = ""
    bank = bank_name
    country = "Россия"
    
    payment_details_text = f"""<b>💳 Реквизиты для оплаты заявки №{order_id}</b>

<b>⏰ ОБЯЗАТЕЛЬНО ОПЛАТИТЕ ЗАЯВКУ В ТЕЧЕНИЕ 10 МИНУТ!</b>
ЕСЛИ НЕ УСПЕВАЕТЕ ОПЛАТИТЬ, ТО СОЗДАЙТЕ НОВУЮ ЗАЯВКУ /start

<b>⚡️ Важно:</b>
• Отправьте <u>точную сумму</u> — это нужно, чтобы система автоматически распознала перевод.
• После оплаты ничего нажимать не нужно — бот сам обработает платёж.
• Проверка и зачисление могут занять до <b>10 минут</b>.

────────────────────
<b>💳 Карта:</b> <code>{card}</code>
<b>👤 Получатель:</b> <code>{recipient}</code>
<b>🏦 Банк:</b> {bank}
<b>💰 Сумма:</b> {final_sum}.00  ₽
<b>🌍 Страна:</b> {country}
────────────────────"""
    
    await callback.message.answer(payment_details_text, reply_markup=requisites_action_buttons())
    
    await send_message_to_channel(
        bot=callback.bot,
        data={
            "username": "@" + callback.message.chat.username if callback.message.chat.username else str(callback.message.chat.id),
            "currency": currency,
            "value_crypto": value_crypto,
            "value_rub": value_rub,
            "unit": unit,
            "priority": priority,
            "final_sum": final_sum,
            "order_id": order_id,
            "payment_method_index": payment_method_index,
            "method_name": method_name,
            "wallet": cosh
        }
    )
    
    await callback.answer()


@buy_router.callback_query(F.data == "requisites_cancel")
async def callback_requisites_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await manager.delete_message(callback.message.chat.id)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Главное меню", callback_data="main_menu")]
    ])
    await callback.message.answer("❌ Заявка отменена", reply_markup=kb)
    await callback.answer()


@buy_router.callback_query(F.data == "requisites_paid")
async def callback_requisites_paid(callback: CallbackQuery, state: FSMContext) -> None:
    receipt_text = """📸 Отправьте чек об оплате
    
Вы можете отправить фото или PDF-файл с чеком об оплате."""
    await callback.message.answer(receipt_text)
    await state.set_state(BuyCryptoState.waiting_receipt)
    await callback.answer()


@buy_router.callback_query(F.data.startswith('order_cancel_'))
async def callback_order_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    order_id = callback.data.replace("order_cancel_", "")
    await state.clear()
    await manager.delete_message(callback.message.chat.id)
    from src.keyboards.user import home_button
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    back_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Главное меню", callback_data="main_menu")]
        ]
    )
    new_message = await callback.message.answer("❌ Заявка отменена", reply_markup=back_keyboard)
    await manager.set_message(callback.message.chat.id, new_message)
    await callback.answer()


@buy_router.message(BuyCryptoState.waiting_receipt, F.photo | F.document)
async def process_receipt(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("order_id")
    
    if not order_id:
        await message.answer("❌ Ошибка: заявка не найдена")
        await state.clear()
        return
    
    receipt_file_id = None
    receipt_type = None
    
    if message.photo:
        receipt_file_id = message.photo[-1].file_id
        receipt_type = "photo"
    elif message.document:
        if message.document.mime_type and "pdf" in message.document.mime_type.lower():
            receipt_file_id = message.document.file_id
            receipt_type = "document"
        else:
            await message.answer("❌ Пожалуйста, отправьте фото или PDF-файл")
            return
    
    if receipt_file_id:
        from src.utils.orders import update_order_receipt, get_order
        update_order_receipt(order_id, receipt_file_id, receipt_type)
        
        order = get_order(order_id)
        if order:
            from src.utils.group import send_receipt_to_admins
            username = "@" + message.chat.username if message.chat.username else str(message.chat.id)
            order_with_username = {**order, "username": username}
            await send_receipt_to_admins(
                bot=message.bot,
                order_id=order_id,
                order_data=order_with_username,
                receipt_file_id=receipt_file_id,
                receipt_type=receipt_type
            )
        
        await message.answer("✅ Чек принят, ожидайте зачисление в течение 20 минут!")
        await state.clear()
    else:
        await message.answer("❌ Пожалуйста, отправьте фото или PDF-файл")


@buy_router.message(BuyCryptoState.waiting_receipt)
async def process_invalid_receipt(message: Message, state: FSMContext):
    await message.answer("❌ Пожалуйста, отправьте фото или PDF-файл с чеком об оплате")

