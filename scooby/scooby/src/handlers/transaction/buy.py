import asyncio
import uuid
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.handlers.transaction import BTC_RUB_BUY, LTC_RUB_BUY, XMR_RUB_BUY
from src.keyboards.transaction import (
    button_buy_back,
    buy_button,
    buy_button_operation,
    home_button,
    order_buttons,
    priority_button,
    vip_payment_button,
)
from src.states.transaction import BuyCryptoState
from src.texts.transaction import TransactionTexts
from src.utils.group import send_message_to_channel
from src.utils.manager import manager
from src.utils.orders import create_order

buy_router = Router()
texts = TransactionTexts()


@buy_router.callback_query(F.data == 'buy')
async def callback_buy_button(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await manager.delete_main_menu(callback.message.chat.id)
    new_message = await callback.message.answer(texts.get("buy"), reply_markup=buy_button())
    await manager.set_message(callback.message.chat.id, new_message)


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


@buy_router.message(BuyCryptoState.value)
async def process_entered_value(message: Message, state: FSMContext):
    data = await state.get_data()
    payment_method = data.get("payment_method")
    currency = data.get("currency")

    await manager.delete_message(message.chat.id)

    try:
        value_str = message.text.replace(',', '.')
        value = float(value_str)

        if value <= 0:
            raise ValueError("Сумма должна быть больше нуля")

        if currency == "ltc":
            rate = LTC_RUB_BUY
        elif currency == "btc":
            rate = BTC_RUB_BUY
        elif currency == "xmr":
            rate = XMR_RUB_BUY
        else:
            raise ValueError("Неизвестная валюта")

        if payment_method == "rub":
            rub_input = value
            crypto_amount = rub_input / rate
            crypto_rounded = round(crypto_amount, 8)

            new_message = await message.answer(
                texts.get("buy_success_rub", value=int(rub_input), currency=currency.upper(), total_sum=crypto_rounded),
                reply_markup=button_buy_back()
            )

            rub_for_order = int(rub_input)  # рубли без VIP
            crypto_for_order = crypto_rounded

        else:
            crypto_input = value
            rub_amount = crypto_input * rate
            rub_rounded = int(round(rub_amount))

            new_message = await message.answer(
                texts.get("buy_success_crypto", value=crypto_input, currency=currency.upper(), total_sum=rub_rounded),
                reply_markup=button_buy_back()
            )

            rub_for_order = rub_rounded
            crypto_for_order = crypto_input

        # Сохраняем: total_sum всегда рубли без VIP, crypto_amount всегда количество крипты
        await state.update_data(
            value=value,
            total_sum=rub_for_order,       # всегда рубли без VIP
            crypto_amount=crypto_for_order # всегда количество крипты
        )

        await state.set_state(BuyCryptoState.cosh)
        await manager.set_message(message.chat.id, new_message)


    except ValueError:
        error_text = texts.get("error_buy")
        if payment_method == "rub":
            prompt_text = texts.get("buy_operation_ru")
        else:
            prompt_text = texts.get("buy_currency", currency=currency.upper())

        new_message = await message.answer(error_text + "\n\n" + prompt_text)
        await manager.set_message(message.chat.id, new_message)


@buy_router.message(BuyCryptoState.cosh)
async def process_wallet(message: Message, state: FSMContext):
    await manager.delete_message(message.chat.id)
    data = await state.get_data()

    wallet = message.text.strip()

    if not wallet:
        await message.answer("❌ Кошелёк не может быть пустым. Повторите ввод.")
        return

    await state.update_data(cosh=wallet)  # или wallet=wallet, как тебе удобнее

    rub_base = data.get("total_sum")  # рубли без VIP
    vip_fee = 300
    vip_sum = rub_base + vip_fee


    # Считаем реальные суммы к оплате (с комиссией 30%)
    normal_with_fee = int(rub_base * 1.2)
    vip_with_fee = normal_with_fee + 300

    new_message = await message.answer(
        texts.get("buy_success_upload_rub",
                 cosh=wallet,
                 total_sum=rub_base,
                 vip_sum=vip_sum,
                 vip_fee=vip_fee,
                 vip_price=vip_with_fee,
                 normal_with_fee=normal_with_fee,  # ← новая реальная сумма обычного
                 vip_with_fee=vip_with_fee,
                 currency=data.get("currency").upper()),
        reply_markup=priority_button()
    )
    await manager.set_message(message.chat.id, new_message)


@buy_router.callback_query(F.data == 'priority_vip')
async def callback_priority_vip(callback: CallbackQuery, state: FSMContext):
    await manager.delete_message(callback.message.chat.id)
    data = await state.get_data()

    rub_base = data.get("total_sum")              # рубли без VIP и без комиссии
    crypto_amount = data.get("crypto_amount")
    wallet = data.get("cosh")
    currency = data.get("currency").upper()

    # Сначала считаем обычную сумму с комиссией 30%
    normal_with_fee = int(rub_base * 1.2)

    # VIP: +300 рублей к уже посчитанной сумме с комиссией
    vip_price = normal_with_fee + 300

    vip_text = f"""💎 VIP-Приоритет 💎
💵 Сумма к оплате: <b>{vip_price} рублей</b>
⏰ Транзакция в течение 10 минут
✅ Обход очереди

🔘 Количество монет: {crypto_amount:.8f} {currency}
💳 Кошелёк: <code>{wallet}</code>

🟢 Загруженность сети {currency}: Низкая
⏰ Время первого подтверждения: 5-20 минут

🪄 Выберите способ оплаты"""

    # Сохраняем в state реальную сумму, которую пользователь заплатит
    await state.update_data(priority="vip", final_payment=vip_price)

    new_message = await callback.message.answer(vip_text, reply_markup=vip_payment_button())
    await manager.set_message(callback.message.chat.id, new_message)

@buy_router.callback_query(F.data == 'priority_normal')
async def callback_priority_normal(callback: CallbackQuery, state: FSMContext):
    await manager.delete_message(callback.message.chat.id)
    data = await state.get_data()

    rub_base = data.get("total_sum")              # рубли без VIP
    crypto_amount = data.get("crypto_amount")     # правильное количество монет
    wallet = data.get("cosh")
    currency = data.get("currency").upper()

    final_sum = rub_base  # без доплаты
    normal_with_fee = int(final_sum * 1.2)

    normal_text = f"""🍀 Обычный приоритет 🍀
💵 Сумма сделки: {normal_with_fee} рублей
🔘 Количество монет к покупки: {crypto_amount:.8f} {currency}
💳 Кошелек: <code>{wallet}</code>
🟢 Загруженность сети {currency}: Низкая
⏰ Время первого подтверждения: 5-20 минут

⏳ Время отправки транзакции 15 минут
🪄 Создайте заявку или примените скидки"""

    await state.update_data(priority="normal", final_sum=final_sum)

    new_message = await callback.message.answer(
        normal_text,
        reply_markup=vip_payment_button()
    )
    await manager.set_message(callback.message.chat.id, new_message)


@buy_router.callback_query(F.data.startswith('payment_'))
async def callback_payment_method(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    payment_method_callback = callback.data

    loading_message = await callback.message.answer("⏳ Формируем заявку, это займет пару секунд...")
    await asyncio.sleep(3)
    await loading_message.delete()

    data = await state.get_data()

    rub_base = data.get("total_sum")            # всегда рубли без VIP (int)
    crypto_amount = data.get("crypto_amount")   # всегда количество крипты (float)
    currency = data.get("currency")
    payment_method_type = data.get("payment_method")  # "rub" или "crypto"
    cosh = data.get("cosh")
    priority = data.get("priority", "normal")

    # Финальная сумма с VIP
    base_with_fee = int(rub_base * 1.2)
    final_sum_with_fee = base_with_fee + 300 if priority == "vip" else base_with_fee


    # Определяем unit для отображения
    unit = "RUB" if payment_method_type == "rub" else currency.upper()
    currency_display = currency.upper()

    order_id = str(uuid.uuid4())
    expires_at = datetime.now() + timedelta(minutes=60)
    expires_str = expires_at.strftime("%H:%M %d.%m")

    order_text = f"""📜 Заявка {order_id}
⏰ Заявка действует до {expires_str} по МСК (60 мин)

💳 Адрес: <code>{cosh}</code>
🪙 Монет: {crypto_amount:.8f} {currency_display}
💸 Сумма к оплате: {final_sum_with_fee} RUB

⏳ В порядке очереди к вашей заявке будет назначен оператор
✉️ Как только это произойдет — вы получите сообщение от него прямо в боте.
💬 При необходимости вы можете написать оператору прямо здесь, в боте."""

    await manager.delete_message(callback.message.chat.id)
    new_message = await callback.message.answer(order_text, reply_markup=order_buttons(order_id))
    await manager.set_message(callback.message.chat.id, new_message)

    # Сохраняем в ордер уже с комиссией
    create_order(order_id, callback.message.chat.id, {
        "currency": currency,
        "value_crypto": crypto_amount,
        "value_rub": rub_base,
        "unit": unit,
        "priority": priority,
        "final_sum": final_sum_with_fee,   # 👈 сохраняем с комиссией
        "payment_method": payment_method_callback,
        "wallet": cosh
    })

    await send_message_to_channel(
        bot=callback.bot,
        data={
            "username": "@" + (callback.from_user.username or str(callback.from_user.id)),
            "final_sum": final_sum_with_fee,
            "currency": currency,
            "value_crypto": crypto_amount,
            "value_rub": rub_base,
            "unit": unit,
            "priority": priority,
            "order_id": order_id,
            "payment_method": payment_method_callback,
            "wallet": cosh
        }
    )

    await state.clear()

    await asyncio.sleep(2)

    await callback.message.answer(
        "Здравствуйте! 👋\n"
        "Мы уже подготавливаем реквизиты для вашей заявки.\n"
        "Подскажите, пожалуйста, с какого банка будете переводить?\n"
        "✍️ Ответ напишите прямо здесь, в этом чате!"
    )

@buy_router.callback_query(F.data.startswith('order_status_'))
async def callback_order_status(callback: CallbackQuery) -> None:
    callback.data.replace("order_status_", "")
    await callback.answer("📊 Ваше место в очереди: 10+", show_alert=True)


@buy_router.callback_query(F.data.startswith('order_cancel_'))
async def callback_order_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    callback.data.replace("order_cancel_", "")
    await state.clear()
    await manager.delete_message(callback.message.chat.id)
    new_message = await callback.message.answer("❌ Заявка отменена", reply_markup=home_button())
    await manager.set_message(callback.message.chat.id, new_message)
    await callback.answer()
