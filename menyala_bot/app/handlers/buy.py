from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..constants import COINS
from ..context import AppContext
from ..keyboards import (
    kb_admin_order_confirm,
    kb_buy_order_actions,
    kb_buy_payment_methods,
    kb_cancel,
    kb_main_menu,
)
from ..states import UserState
from ..telegram_helpers import callback_message, callback_user_id, message_user_id
from ..utils import fmt_coin, fmt_money, parse_amount, safe_username


def build_buy_router(ctx: AppContext) -> Router:
    router = Router(name="buy")

    coin_text_map = {
        "🔄 Купить BTC": "btc",
        "🔄 Купить LTC": "ltc",
        "🔄 Купить XMR": "xmr",
        "🔄 Купить USDT-TRC20": "usdt",
    }

    async def send_admin_new_order(message: Message, order_id: str) -> None:
        order = ctx.orders.get_order(order_id)
        if order is None:
            return
        bot = message.bot
        if bot is None:
            return
        username = safe_username(order["username"])
        text = (
            "🆕 Новый заказ!\n\n"
            f"📦 ID заказа: {order['order_id']}\n"
            f"👤 ID: {order['user_id']}\n"
            f"📝 Username: {username}\n"
            "👛 Кошелек:\n"
            f"<code>{order['wallet']}</code>\n\n"
            f"💎 Крипта: {fmt_coin(order['coin_amount'])} {order['coin_symbol']}\n"
            f"💰 Сумма: {fmt_money(order['amount_rub'])} RUB\n"
            f"💳 Способ оплаты: {order['payment_method']}"
        )
        for admin_id in ctx.admin_ids:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=text,
                    reply_markup=kb_admin_order_confirm(order_id),
                )
            except Exception:
                continue

    @router.message(F.text.in_(set(coin_text_map.keys())))
    async def buy_choose_coin(message: Message, state: FSMContext) -> None:
        text = message.text or ""
        coin_key = coin_text_map.get(text)
        if coin_key is None:
            return
        await state.set_state(UserState.waiting_buy_amount)
        await state.update_data(buy_coin=coin_key)
        symbol = COINS[coin_key]["symbol"]
        await message.answer(
            f"💰 Введи нужную сумму в {symbol} или в <b>RUB</b>:\n\n"
            "<b>Мин. сумма: 1000 руб.</b>\n"
            "<b>Макс. сумма: 150000 руб.</b>",
            reply_markup=kb_cancel(),
        )
        await message.answer("Например: <b>0.00041</b> или <b>1000</b>", reply_markup=kb_cancel())

    @router.callback_query(F.data == "buy:flow:cancel")
    async def buy_cancel_flow(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await callback.answer("Заявка отменена")
        msg = callback_message(callback)
        if msg is not None:
            await msg.answer("❌ Заявка отменена.")

    @router.message(UserState.waiting_buy_amount)
    async def buy_input_amount(message: Message, state: FSMContext) -> None:
        raw_text = (message.text or "").strip().replace(",", ".")
        amount_value = parse_amount(raw_text)
        if amount_value is None:
            await message.answer("Введите корректную сумму, например: 0.00041 или 2400")
            return

        data = await state.get_data()
        coin_key = data.get("buy_coin", "btc")
        rates = await ctx.rates.get_rates()
        rate = rates.get(coin_key, 1.0)

        is_coin_input = amount_value < 1
        base_rub = amount_value * rate if is_coin_input else amount_value
        if base_rub < 1000 or base_rub > 150000:
            await message.answer("Сумма должна быть в диапазоне 1000..150000 RUB")
            return

        commission_percent = ctx.settings.commission_percent
        commission_rub = base_rub * commission_percent / 100
        amount_to_pay_rub = base_rub + commission_rub
        amount_coin = amount_value if is_coin_input else base_rub / max(rate, 0.0000001)
        amount_coin = max(amount_coin, 0.0)
        symbol = COINS[coin_key]["symbol"]

        await state.update_data(
            buy_amount_rub=amount_to_pay_rub,
            buy_base_rub=base_rub,
            buy_commission_rub=commission_rub,
            buy_amount_coin=amount_coin,
            buy_symbol=symbol,
        )

        pay_rub = int(round(amount_to_pay_rub))
        text = (
            "До бонусного обмена осталось 7 обм.\n\n"
            f"Получите: <b>{fmt_coin(amount_coin)} {symbol}</b>\n"
            f"К оплате: <b>{pay_rub} ₽</b>\n\n"
            "<u>Выберите способ оплаты</u>⬇️"
        )
        await message.answer(
            text,
            reply_markup=kb_buy_payment_methods(ctx.settings.payment_methods()),
        )

    @router.callback_query(F.data.startswith("buy:method:"))
    async def buy_choose_method(callback: CallbackQuery, state: FSMContext) -> None:
        raw_index = (callback.data or "").split(":")[-1]
        if not raw_index.isdigit():
            await callback.answer("Некорректный способ оплаты", show_alert=True)
            return
        method_index = int(raw_index)
        methods = ctx.settings.payment_methods()
        if method_index < 0 or method_index >= len(methods):
            await callback.answer("Способ оплаты не найден", show_alert=True)
            return

        await callback.answer()
        await state.update_data(payment_method=methods[method_index])
        await state.set_state(UserState.waiting_buy_wallet)
        msg = callback_message(callback)
        if msg is not None:
            symbol = (await state.get_data()).get("buy_symbol", "BTC")
            await msg.answer(f"Введите ваш {symbol} кошелек:", reply_markup=kb_cancel())

    @router.message(UserState.waiting_buy_wallet)
    async def buy_input_wallet(message: Message, state: FSMContext) -> None:
        wallet = (message.text or "").strip()
        if len(wallet) < 10:
            await message.answer("Кошелек слишком короткий. Введите корректный адрес.")
            return

        user_id = message_user_id(message)
        if user_id is None:
            await message.answer("Не удалось определить пользователя.")
            return

        data = await state.get_data()
        amount_rub = float(data.get("buy_amount_rub", 0.0))
        amount_coin = float(data.get("buy_amount_coin", 0.0))
        symbol = str(data.get("buy_symbol", "BTC"))
        payment_method = str(data.get("payment_method", "Перевод на карту"))
        bank, requisites_value = ctx.settings.method_requisites(payment_method)

        order = ctx.orders.create_order(
            user_id=user_id,
            username=(message.from_user.username if message.from_user else "") or "",
            wallet=wallet,
            coin_symbol=symbol,
            coin_amount=amount_coin,
            amount_rub=amount_rub,
            payment_method=payment_method,
            bank=bank,
        )
        ctx.users.record_trade(
            user_id=user_id,
            side="buy",
            coin=symbol,
            amount_coin=amount_coin,
            amount_rub=amount_rub,
        )
        await state.clear()

        pay_rub_int = int(round(amount_rub))
        text = (
            "⚠ ВРЕМЯ НА ОПЛАТУ 30 МИНУТ.\n\n"
            f"📦 Номер заявки: <b>{order['order_id']}</b>\n"
            f"🏦 Банк: <b>{bank}</b>\n"
            f"💳 Реквизиты: <code>{requisites_value}</code>\n"
            f"💰 Сумма к оплате: <b>{pay_rub_int} RUB</b>\n"
            f"💎 К получению: <b>{fmt_coin(amount_coin)} {symbol}</b>\n"
            f"👛 Кошелек: <b>{wallet}</b>\n\n"
            f"💳 Способ оплаты: <b>{payment_method}</b>\n"
            "После оплаты нажмите «<b>✅ Я оплатил</b>»."
        )
        await message.answer(text, reply_markup=kb_buy_order_actions(order["order_id"]))

    @router.callback_query(F.data.startswith("buy:cancel:"))
    async def buy_cancel_order(callback: CallbackQuery, state: FSMContext) -> None:
        order_id = (callback.data or "").split(":")[-1]
        user_id = callback_user_id(callback)
        order = ctx.orders.get_order(order_id)
        if user_id is None or order is None or order["user_id"] != user_id:
            await callback.answer("Заявка не найдена", show_alert=True)
            return
        await state.clear()
        if order["status"] == "paid":
            await callback.answer("Заявка уже в обработке. Возвращаем в меню.")
            msg = callback_message(callback)
            if msg is not None:
                await msg.answer("⬇ Выберите меню ниже:", reply_markup=kb_main_menu())
            return
        ctx.orders.mark_cancelled(order_id)
        await callback.answer("Заявка отменена")
        msg = callback_message(callback)
        if msg is not None:
            await msg.edit_text("❌ Заявка отменена.")
            await msg.answer("⬇ Выберите меню ниже:", reply_markup=kb_main_menu())

    @router.callback_query(F.data.startswith("buy:paid:"))
    async def buy_mark_paid(callback: CallbackQuery, state: FSMContext) -> None:
        order_id = (callback.data or "").split(":")[-1]
        user_id = callback_user_id(callback)
        order = ctx.orders.get_order(order_id)
        if user_id is None or order is None or order["user_id"] != user_id:
            await callback.answer("Заявка не найдена", show_alert=True)
            return
        if not ctx.orders.mark_paid(order_id):
            await callback.answer("Статус заявки нельзя изменить", show_alert=True)
            return
        await callback.answer("Платеж отмечен.", show_alert=True)
        await state.set_state(UserState.waiting_buy_receipt)
        await state.update_data(waiting_receipt_order_id=order_id)
        msg = callback_message(callback)
        if msg is not None:
            await msg.answer("Пожалуйста, прикрепите чек в виде скриншота одним сообщением.")

    @router.message(UserState.waiting_buy_receipt, F.photo)
    async def buy_receipt_photo(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        order_id = str(data.get("waiting_receipt_order_id") or "")
        order = ctx.orders.get_order(order_id)
        if order is None:
            await state.clear()
            await message.answer("Заявка не найдена.")
            return

        await state.clear()
        await send_admin_new_order(message, order_id)

        bot = message.bot
        if bot is not None:
            caption = (
                "🧾 <b>Чек по заявке</b>\n"
                f"📦 ID заказа: {order_id}\n"
                f"👤 ID клиента: {order['user_id']}\n"
                f"💰 Сумма: <b>{fmt_money(order['amount_rub'])} RUB</b>"
            )
            photos = message.photo or []
            if not photos:
                await message.answer("Не удалось получить изображение чека, отправьте еще раз.")
                return
            photo = photos[-1]
            for admin_id in ctx.admin_ids:
                try:
                    await bot.send_photo(chat_id=admin_id, photo=photo.file_id, caption=caption)
                except Exception:
                    continue

        await message.answer("✅")
        await message.answer("Чек принят, ожидайте зачисление в течение 20 минут.")

    @router.message(UserState.waiting_buy_receipt)
    async def buy_receipt_invalid(message: Message) -> None:
        await message.answer("Пожалуйста, отправьте чек скриншотом.")

    return router
