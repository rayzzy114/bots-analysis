import asyncio
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..constants import BUY_BUTTON_TO_COIN, COINS
from ..context import AppContext
from ..keyboards import (
    kb_admin_order_confirm,
    kb_buy_donation_step,
    kb_buy_next_step,
    kb_buy_order_actions,
    kb_buy_payment_methods,
    kb_buy_wallet_choice,
    kb_cancel,
    kb_main_menu,
)
from ..states import UserState
from ..telegram_helpers import answer_photo_with_retry, callback_message, callback_user_id, message_user_id
from ..utils import fmt_coin, fmt_money, parse_amount, safe_username


DONATION_TEXT = (
    "У тебя всегда есть выбор! Хочешь пожертвовать 💔 свою скидку\n"
    "Фонд «Подарок Ангелу» создан в 2014 году для оказания\n"
    "комплексной помощи и поддержки семей, в которых\n"
    "воспитываются дети с нарушением опорно-двигательного\n"
    "аппарата. ПОДАРОК АНГЕЛУ ?"
)


def build_buy_router(ctx: AppContext, assets_dir: str) -> Router:
    router = Router(name="buy")
    assets_path = Path(assets_dir)
    unavailable_buy_coins = {"trx", "eth", "xmr"}

    def default_payment_method() -> str:
        methods = ctx.settings.payment_methods()
        if methods:
            return methods[0]
        return "Номер карты (2211 руб.)"

    def clean_method_name(raw_value: str) -> str:
        return raw_value.split(" (")[0].strip()

    def format_pay_line(pay_before: int, pay_after: int, symbol: str) -> str:
        if symbol == "USDT":
            return f"К оплате: <s>{pay_before} ₽</s> > <code>{pay_after} ₽</code>"
        return f"К оплате: {pay_before} ₽ > <code>{pay_after} ₽</code>"

    def build_payment_method_options(pay_after: int) -> tuple[list[str], list[dict[str, int | str]]]:
        options: list[str] = []
        payload: list[dict[str, int | str]] = []
        for method in ctx.settings.payment_methods():
            clean_name = clean_method_name(method)
            method_amount = pay_after
            if "СБП" in clean_name.upper():
                method_amount = max(1, pay_after - 100)
            title = f"{clean_name} ({method_amount} руб.)"
            options.append(title)
            payload.append({"method": method, "pay_after": method_amount, "clean_method": clean_name})
        return options, payload

    def detect_coin_input(raw_text: str, amount_value: float, rate: float) -> bool:
        if "." in raw_text:
            return True
        rub_if_coin = amount_value * rate
        rub_if_rub = amount_value
        coin_in_range = 1000 <= rub_if_coin <= 150000
        rub_in_range = 1000 <= rub_if_rub <= 150000
        if coin_in_range and not rub_in_range:
            return True
        if rub_in_range and not coin_in_range:
            return False
        if amount_value < 1:
            return True
        return False

    def amount_prompt_payload(coin_key: str, symbol: str) -> tuple[Path, str, str, str]:
        if coin_key == "usdt":
            return (
                assets_path / "buy_amount_prompt_usdt.jpg",
                "💰 Введи нужную сумму в <b>USDT</b>:",
                "Например: <b>10</b>",
                "Введите корректную сумму, например: <b>10</b>",
            )
        if coin_key == "ltc":
            return (
                assets_path / "buy_amount_prompt_ltc.jpg",
                f"💰 Введи нужную сумму в <b>{symbol}</b> или в <b>RUB</b>:",
                "Например: <b>0.18</b> или <b>1000</b>",
                "Введите корректную сумму, например: <b>0.18</b> или <b>2400</b>",
            )
        return (
            assets_path / "buy_amount_prompt.jpg",
            f"💰 Введи нужную сумму в <b>{symbol}</b> или в <b>RUB</b>:",
            "Например: <b>0.00041</b> или <b>1000</b>",
            "Введите корректную сумму, например: <b>0.00041</b> или <b>2400</b>",
        )

    def wallet_prompt_path(symbol: str) -> Path:
        symbol_upper = symbol.upper()
        if symbol_upper == "USDT":
            return assets_path / "buy_wallet_prompt_usdt.jpg"
        if symbol_upper == "LTC":
            return assets_path / "buy_wallet_prompt_ltc.jpg"
        return assets_path / "buy_wallet_prompt.jpg"

    def unavailable_text(symbol: str) -> str:
        return (
            f"⚙️ Извините, обмен <b>{symbol}</b> временно недоступен по одной из двух причин:\n\n"
            f"📶 Сеть <b>{symbol}</b> перегружена;\n"
            "💵 Обменный пункт пополняет резервы;"
        )

    async def send_main_menu(message: Message, state: FSMContext | None = None) -> None:
        if state is not None:
            await state.clear()
        await answer_photo_with_retry(
            message=message,
            photo_path=assets_path / "menu_main.jpg",
            caption="⬇ Выберите меню ниже:",
            reply_markup=kb_main_menu(),
        )

    async def send_admin_new_order(message: Message, order_id: str) -> None:
        order = ctx.orders.get_order(order_id)
        if order is None:
            return
        bot = message.bot
        if bot is None:
            return
        receipt_file_id = message.photo[-1].file_id if message.photo else None
        username = safe_username(order["username"])
        text = (
            "🆕 Новый заказ!\n\n"
            f"📦 ID заказа: {order['order_id']}\n"
            f"👤 ID: {order['user_id']}\n"
            f"📝 Username: {username}\n"
            "👛 Кошелек:\n"
            f"<code>{order['wallet']}</code>\n\n"
            f"💎 Крипта: <b>{fmt_coin(order['coin_amount'])} {order['coin_symbol']}</b>\n"
            f"💰 Сумма: <b>{fmt_money(order['amount_rub'])} RUB</b>\n"
            f"💳 Способ оплаты: {order['payment_method']}"
        )
        for admin_id in ctx.admin_ids:
            if receipt_file_id:
                try:
                    await bot.send_photo(
                        chat_id=admin_id,
                        photo=receipt_file_id,
                        caption=f"🧾 Чек по заказу #{order_id}",
                    )
                except Exception:
                    pass
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=text,
                    reply_markup=kb_admin_order_confirm(order_id),
                )
            except Exception:
                continue

    @router.message(UserState.waiting_buy_amount, CommandStart())
    @router.message(UserState.waiting_buy_confirm, CommandStart())
    @router.message(UserState.waiting_buy_wallet, CommandStart())
    @router.message(UserState.waiting_buy_receipt, CommandStart())
    @router.message(UserState.waiting_buy_amount, F.text == "❌ Отмена")
    @router.message(UserState.waiting_buy_confirm, F.text == "❌ Отмена")
    @router.message(UserState.waiting_buy_wallet, F.text == "❌ Отмена")
    @router.message(UserState.waiting_buy_receipt, F.text == "❌ Отмена")
    async def buy_force_exit(message: Message, state: FSMContext) -> None:
        await send_main_menu(message, state)

    @router.message(F.text.in_(set(BUY_BUTTON_TO_COIN.keys())))
    async def buy_choose_coin(message: Message, state: FSMContext) -> None:
        coin_key = BUY_BUTTON_TO_COIN.get(message.text or "")
        if coin_key is None:
            return
        symbol = COINS[coin_key]["symbol"]
        if coin_key in unavailable_buy_coins:
            await state.clear()
            await message.answer(unavailable_text(symbol))
            return

        photo_path, caption, example_text, invalid_amount_hint = amount_prompt_payload(coin_key, symbol)
        input_mode = "coin_only" if coin_key == "usdt" else "coin_or_rub"
        await state.set_state(UserState.waiting_buy_amount)
        await state.update_data(
            buy_coin=coin_key,
            buy_input_mode=input_mode,
            buy_invalid_amount_hint=invalid_amount_hint,
        )
        await answer_photo_with_retry(
            message=message,
            photo_path=photo_path,
            caption=caption,
        )
        await message.answer(example_text, reply_markup=kb_cancel())

    @router.callback_query(F.data == "buy:flow:cancel")
    async def buy_cancel_flow(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await callback.answer("Заявка отменена")
        msg = callback_message(callback)
        if msg is not None:
            await send_main_menu(msg)

    @router.message(UserState.waiting_buy_amount)
    async def buy_input_amount(message: Message, state: FSMContext) -> None:
        raw_text = (message.text or "").strip().replace(",", ".")
        amount_value = parse_amount(raw_text)
        data = await state.get_data()
        if amount_value is None:
            invalid_hint = str(data.get("buy_invalid_amount_hint", "Введите корректную сумму."))
            await message.answer(invalid_hint)
            return

        coin_key = data.get("buy_coin", "btc")
        rates = await ctx.rates.get_rates()
        rate = rates.get(coin_key, 1.0)

        input_mode = str(data.get("buy_input_mode", "coin_or_rub"))
        is_coin_input = True if input_mode == "coin_only" else detect_coin_input(raw_text, amount_value, rate)
        symbol = COINS[coin_key]["symbol"]
        min_coin_map: dict[str, float] = {
            "btc": 0.00041,
            "ltc": 0.18,
            "usdt": 10.0,
        }
        max_coin_value = 150000 / max(rate, 0.0000001)
        if is_coin_input:
            min_coin_value = min_coin_map.get(coin_key, 1000 / max(rate, 0.0000001))
            if amount_value < min_coin_value or amount_value > max_coin_value:
                await message.answer(
                    f"Сумма должна быть в диапазоне <b>{fmt_coin(min_coin_value)}..{fmt_coin(max_coin_value)} {symbol}</b>"
                )
                return
            base_rub = amount_value * rate
        else:
            base_rub = amount_value
            if base_rub < 1000 or base_rub > 150000:
                await message.answer("Сумма должна быть в диапазоне <b>1000..150000 RUB</b>")
                return

        commission_percent = ctx.settings.commission_percent
        commission_rub = base_rub * commission_percent / 100
        amount_to_pay_rub = base_rub + commission_rub
        amount_coin = amount_value if is_coin_input else base_rub / max(rate, 0.0000001)

        discount_rub = 27
        pay_before = int(round(amount_to_pay_rub))
        pay_after = max(1, pay_before - discount_rub)

        method_titles, method_payload = build_payment_method_options(pay_after)

        await state.update_data(
            buy_amount_rub=pay_after,
            buy_amount_coin=amount_coin,
            buy_symbol=symbol,
            payment_method=default_payment_method(),
            buy_pay_before=pay_before,
            buy_pay_after=pay_after,
            buy_discount_rub=discount_rub,
            buy_donation=False,
            buy_method_options=method_payload,
        )
        await state.set_state(UserState.waiting_buy_confirm)

        text = (
            f"Получите: <b>{fmt_coin(amount_coin)} {symbol}</b>\n"
            f"Скидка: <b>{discount_rub} ₽</b>\n\n"
            "<u>Выберите способ оплаты⬇️</u>"
        )
        await message.answer(text, reply_markup=kb_buy_payment_methods(method_titles))

    @router.callback_query(UserState.waiting_buy_confirm, F.data.startswith("buy:method:"))
    async def buy_pick_method(callback: CallbackQuery, state: FSMContext) -> None:
        await callback.answer()
        msg = callback_message(callback)
        if msg is None:
            return
        data = await state.get_data()
        method_options = data.get("buy_method_options")
        if not isinstance(method_options, list):
            await msg.answer("Сессия устарела. Нажмите /start и начните заново.")
            return

        raw_index = (callback.data or "").split(":")[-1]
        if not raw_index.isdigit():
            await msg.answer("Выберите способ оплаты кнопками ниже.")
            return
        method_index = int(raw_index)
        if method_index < 0 or method_index >= len(method_options):
            await msg.answer("Выберите способ оплаты кнопками ниже.")
            return

        method_data = method_options[method_index]
        if not isinstance(method_data, dict):
            await msg.answer("Выберите способ оплаты кнопками ниже.")
            return

        method_title = str(method_data.get("method", default_payment_method()))
        pay_after = int(method_data.get("pay_after", data.get("buy_pay_after", 0)))
        discount_rub = int(data.get("buy_discount_rub", 27))
        pay_before = pay_after + discount_rub
        amount_coin = float(data.get("buy_amount_coin", 0.0))
        symbol = str(data.get("buy_symbol", "BTC"))
        clean_method = str(method_data.get("clean_method", clean_method_name(method_title)))

        await state.update_data(
            payment_method=method_title,
            buy_pay_before=pay_before,
            buy_pay_after=pay_after,
            buy_amount_rub=pay_after,
            buy_donation=False,
        )

        text = (
            "До бонусного обмена осталось 9 обм.\n\n"
            f"Способ оплаты: <b>{clean_method}</b>\n"
            f"Получите: <b>{fmt_coin(amount_coin)} {symbol}</b>\n"
            f"Скидка: <b>{discount_rub} ₽</b>\n"
            f"{format_pay_line(pay_before, pay_after, symbol)}\n\n"
            "<u>Выберите способ оплаты⬇️</u>"
        )
        await msg.answer(text, reply_markup=kb_buy_next_step())

    @router.callback_query(F.data == "buy:next")
    async def buy_show_donation_step(callback: CallbackQuery, state: FSMContext) -> None:
        await callback.answer()
        msg = callback_message(callback)
        if msg is None:
            return
        data = await state.get_data()
        amount_coin = float(data.get("buy_amount_coin", 0))
        symbol = str(data.get("buy_symbol", "BTC"))
        pay_before = int(data.get("buy_pay_before", 0))
        pay_after = int(data.get("buy_pay_after", 0))

        if amount_coin <= 0 or pay_before <= 0:
            await msg.answer("Сессия устарела. Нажмите /start и начните заново.")
            return

        await msg.answer(
            f"Получишь: <b>{fmt_coin(amount_coin)} {symbol}</b>\n"
            f"{format_pay_line(pay_before, pay_after, symbol)}\n\n"
            f"{DONATION_TEXT}",
            reply_markup=kb_buy_donation_step(),
        )

    @router.callback_query(F.data.in_({"buy:donation:yes", "buy:donation:no"}))
    async def buy_donation_toggle(callback: CallbackQuery, state: FSMContext) -> None:
        donate = callback.data == "buy:donation:yes"
        data = await state.get_data()
        pay_before = int(data.get("buy_pay_before", 0))
        pay_after = int(data.get("buy_pay_after", 0))
        selected_amount = pay_before if donate and pay_before > 0 else pay_after

        await state.update_data(
            buy_donation=donate,
            buy_amount_rub=selected_amount,
        )
        await callback.answer("Выбрано: Да" if donate else "Выбрано: Нет")

    @router.callback_query(F.data == "buy:next:wallet")
    async def buy_next_wallet(callback: CallbackQuery, state: FSMContext) -> None:
        await callback.answer()
        msg = callback_message(callback)
        if msg is None:
            return

        data = await state.get_data()
        symbol = str(data.get("buy_symbol", "BTC"))
        wallet_photo_path = wallet_prompt_path(symbol)
        await state.set_state(UserState.waiting_buy_wallet)
        await answer_photo_with_retry(
            message=msg,
            photo_path=wallet_photo_path,
            caption=f"Введите свой <b>{symbol}</b> адрес:",
            reply_markup=kb_buy_wallet_choice(),
        )

    @router.message(UserState.waiting_buy_wallet)
    async def buy_input_wallet(message: Message, state: FSMContext) -> None:
        wallet = (message.text or "").strip()
        if wallet == "💸 На мой кошелек":
            wallet = "STPPiu0IiqYy"
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
        payment_method = str(data.get("payment_method", default_payment_method()))
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

        await message.answer("⏳ Ожидайте, идет подбор реквизитов")
        await asyncio.sleep(15)

        pay_rub_int = int(round(amount_rub))
        text = (
            f"Перевод (Банк): {bank}\n"
            f"Реквизиты: <code>{requisites_value}</code>\n"
            f"Сумма к оплате: <b>{pay_rub_int} RUB</b>\n"
            f"К получению: <b>{fmt_coin(amount_coin)} {symbol}</b>\n"
            f"На кошелек: <code>{wallet}</code>\n\n"
            "⚠️ Внимание: Переводить точную сумму!\n"
            "🧾 После оплаты нажмите\n"
            '"✅ Я оплатил"\n\n'
            "⏱ На оплату даётся 20 мин!"
        )
        await message.answer(text, reply_markup=kb_buy_order_actions(order["order_id"]))

    @router.callback_query(F.data.startswith("buy:cancel:"))
    async def buy_cancel_order(callback: CallbackQuery) -> None:
        order_id = (callback.data or "").split(":")[-1]
        user_id = callback_user_id(callback)
        order = ctx.orders.get_order(order_id)
        if user_id is None or order is None or order["user_id"] != user_id:
            await callback.answer("Заявка не найдена", show_alert=True)
            return
        ctx.orders.mark_cancelled(order_id)
        await callback.answer("Заявка отменена")
        msg = callback_message(callback)
        if msg is not None:
            await msg.edit_text("❌ Заявка отменена.")

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
            try:
                await msg.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
            await msg.answer("❗ Пожалуйста, прикрепите чек в виде скриншота одним сообщением.")

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
        await message.answer("✅ Чек принят, ожидайте зачисление в течение 20 минут.")

    @router.message(UserState.waiting_buy_receipt)
    async def buy_receipt_invalid(message: Message) -> None:
        await message.answer("Пожалуйста, отправьте чек скриншотом.")

    return router
