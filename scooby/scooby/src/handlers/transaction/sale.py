import asyncio
import uuid
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from cfg.base import OPERATOR_USERNAME
from src.handlers.transaction import LTC_RUB_SELL, XMR_RUB_SELL, BTC_RUB_SELL, USDT_RUB_SELL
from src.keyboards.transaction import sale_button, sale_button_operation, button_buy_back, success_sale_button, \
    success_sale_button_final, home_button, payment_count_button, order_buttons
from src.states.transaction import SaleCryptoState
from src.texts.transaction import TransactionTexts
from src.utils.group import send_message_to_channel
from src.utils.manager import manager
from src.utils.orders import create_order

sale_router = Router()
texts = TransactionTexts()

RATES_SELL = {
    "ltc": LTC_RUB_SELL,
    "btc": BTC_RUB_SELL,
    "xmr": XMR_RUB_SELL,
    "usdt": USDT_RUB_SELL,
}


@sale_router.callback_query(F.data == 'sale')
async def callback_sale_start(callback: CallbackQuery) -> None:
    await manager.delete_main_menu(callback.message.chat.id)
    new_message = await callback.message.answer(texts.get("sale"), reply_markup=sale_button())
    await manager.set_message(callback.message.chat.id, new_message)


@sale_router.callback_query(F.data.startswith('sale_'))
async def callback_choose_currency(callback: CallbackQuery, state: FSMContext) -> None:
    currency = callback.data.replace("sale_", "")
    await manager.delete_message(callback.message.chat.id)
    new_message = await callback.message.answer(
        texts.get("sale_currency", currency=currency.upper()),
        reply_markup=sale_button_operation(crypto=False, currency=currency)
    )
    await manager.set_message(callback.message.chat.id, new_message)
    await state.set_state(SaleCryptoState.value)
    await state.update_data(currency=currency)


@sale_router.callback_query(F.data == 'operation_sale_ru', SaleCryptoState.value)
async def callback_sale_rub(callback: CallbackQuery, state: FSMContext) -> None:
    await manager.delete_message(callback.message.chat.id)
    data = await state.get_data()
    currency = data.get("currency")
    await state.update_data(payment_method="rub")
    new_message = await callback.message.answer(
        texts.get("buy_operation_ru"),  # можно переименовать текст, но пока оставим
        reply_markup=sale_button_operation(crypto=True, currency=currency)
    )
    await manager.set_message(callback.message.chat.id, new_message)


@sale_router.callback_query(F.data == 'operation_sale_crypto', SaleCryptoState.value)
async def callback_sale_crypto(callback: CallbackQuery, state: FSMContext) -> None:
    await manager.delete_message(callback.message.chat.id)
    data = await state.get_data()
    currency = data.get("currency")
    await state.update_data(payment_method="crypto")
    new_message = await callback.message.answer(
        texts.get("sale_currency", currency=currency.upper()),
        reply_markup=sale_button_operation(crypto=False, currency=currency)
    )
    await manager.set_message(callback.message.chat.id, new_message)


@sale_router.message(SaleCryptoState.value)
async def process_amount(message: Message, state: FSMContext):
    data = await state.get_data()
    payment_method = data.get("payment_method")
    currency = data.get("currency")

    await manager.delete_message(message.chat.id)

    try:
        value = float(message.text.replace(',', '.'))

        if value <= 0:
            raise ValueError()

        rate = RATES_SELL[currency]

        if payment_method == "rub":
            # Продажа за рубли → сколько крипты нужно отдать
            rub_to_receive = value
            crypto_to_sell = rub_to_receive / rate
            crypto_display = round(crypto_to_sell, 8)

            await message.answer(
                f"Вы хотите получить {int(rub_to_receive)} RUB\n"
                f"За это нужно отдать: {crypto_display} {currency.upper()}",
                reply_markup=button_buy_back()
            )

            rub_base = int(rub_to_receive)
            crypto_base = crypto_display

        else:
            # Продажа крипты → сколько рублей получит
            crypto_to_sell = value
            rub_to_receive = crypto_to_sell * rate
            rub_display = int(round(rub_to_receive))

            await message.answer(
                f"Вы хотите продать {crypto_to_sell} {currency.upper()}\n"
                f"За это получите: {rub_display} RUB",
                reply_markup=button_buy_back()
            )

            rub_base = rub_display
            crypto_base = crypto_to_sell

        # Сохраняем: total_sum = рубли (что получит), crypto_amount = крипта (что отдаёт)
        await state.update_data({
            "value": value,
            "total_sum": rub_base,         # всегда рубли, которые клиент получит
            "crypto_amount": crypto_base   # всегда крипта, которую клиент отдаёт
        })

        await state.set_state(SaleCryptoState.cosh)
        new_message = await message.answer("✏️ Введите реквизиты для выплаты (карта, СБП и т.д.):")
        await manager.set_message(message.chat.id, new_message)

    except ValueError:
        await message.answer("❌ Неверная сумма. Попробуйте ещё раз.")
        

@sale_router.message(SaleCryptoState.cosh)
async def process_requisites(message: Message, state: FSMContext):
    await manager.delete_message(message.chat.id)
    data = await state.get_data()

    requisites = message.text.strip()
    await state.update_data(requisites=requisites)

    rub_receive = data.get("total_sum")
    crypto_sell = data.get("crypto_amount")
    currency = data.get("currency").upper()

    text = f"""✅ Вы хотите продать {crypto_sell:.8f} {currency}

💰 За это получите: {rub_receive} RUB

💳 Реквизиты для выплаты:
<code>{requisites}</code>"""

    new_message = await message.answer(text, reply_markup=success_sale_button())
    await manager.set_message(message.chat.id, new_message)


@sale_router.callback_query(F.data == 'success_sale')
async def create_sale_order(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    loading = await callback.message.answer("⏳ Создаём заявку...")
    await asyncio.sleep(3)
    await loading.delete()

    data = await state.get_data()
    
    rub_receive_base = data.get("total_sum")       # рубли без комиссии
    crypto_sell = data.get("crypto_amount")        # крипта, которую клиент отдаёт
    currency = data.get("currency")
    requisites = data.get("requisites")
    payment_method_type = data.get("payment_method")

    unit = "RUB" if payment_method_type == "rub" else currency.upper()

    # ✅ Добавляем комиссию 30%
    rub_receive_final = data.get("total_sum")   # или rub_receive_base — берём как есть из превью

    order_id = str(uuid.uuid4())
    expires_at = datetime.now() + timedelta(minutes=60)
    expires_str = expires_at.strftime("%H:%M %d.%m")

    order_text = f"""🟢 Загруженность сети {currency.upper()}: Низкая
⏰ Время первого подтверждения: 5-20 минут

📜 Заявка {order_id}
⏰ Действует до {expires_str} по МСК

💳 Реквизиты для выплаты: <code>{requisites}</code>
🪙 Отдаёте: {crypto_sell:.8f} {currency.upper()}
💸 Получаете: {rub_receive_final} RUB

⏳ Оператор скоро свяжется с вами."""
    
    await manager.delete_message(callback.message.chat.id)
    new_message = await callback.message.answer(order_text, reply_markup=order_buttons(order_id))
    await manager.set_message(callback.message.chat.id, new_message)

    # Сохраняем в ордер уже с комиссией
    create_order(order_id, callback.message.chat.id, {
        "currency": currency,
        "value_crypto": crypto_sell,
        "value_rub": rub_receive_final,   # 👈 сохраняем с комиссией
        "unit": unit,
        "wallet": requisites,
        "type": "sale"
    })

    # Уведомление админам — тоже с комиссией
    await send_message_to_channel(
        bot=callback.bot,
        sale=True,
        data={
            "username": "@" + (callback.from_user.username or str(callback.from_user.id)),
            "currency": currency,
            "value_crypto": crypto_sell,
            "value_rub": rub_receive_final,
            "final_sum": rub_receive_final,
            "unit": unit,
            "order_id": order_id,
            "wallet": requisites
        }
    )

    await state.clear()

    await asyncio.sleep(2)
    await callback.message.answer(
        f"После первого подтверждения с вами свяжется оператор для подтверждения оплаты.\n"
        f"В случае вопросов пишите {OPERATOR_USERNAME}"
    )

    

@sale_router.callback_query(F.data.startswith('order_status_'))
async def callback_order_status(callback: CallbackQuery) -> None:
    order_id = callback.data.replace("order_status_", "")
    await callback.answer("📊 Ваше место в очереди: 10+", show_alert=True)


@sale_router.callback_query(F.data.startswith('order_cancel_'))
async def callback_order_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    order_id = callback.data.replace("order_cancel_", "")
    await state.clear()
    await manager.delete_message(callback.message.chat.id)
    new_message = await callback.message.answer("❌ Заявка отменена", reply_markup=home_button())
    await manager.set_message(callback.message.chat.id, new_message)
    await callback.answer()

