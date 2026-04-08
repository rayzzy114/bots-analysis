import random
import re
from pathlib import Path

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from ..constants import COINS
from ..context import AppContext
from ..keyboards import kb_buy_coins, kb_buy_confirm, kb_buy_method, kb_buy_order_actions, kb_cancel
from ..media import send_screen
from ..states import TradeState
from ..telegram_helpers import callback_message, message_user_id
from ..utils import calc_quote, detect_mode, fmt_coin, parse_amount


def build_buy_router(ctx: AppContext, assets_dir: Path) -> Router:
    router = Router(name="buy")
    min_buy_rub = 1500.0

    def fmt_plain(value: float) -> str:
        return f"{value:.2f}".rstrip("0").rstrip(".")

    def format_card_like(value: str) -> str:
        digits = re.sub(r"\D", "", value)
        if 16 <= len(digits) <= 19:
            return " ".join(digits[i : i + 4] for i in range(0, len(digits), 4))
        return value

    @router.callback_query(F.data == "menu:buy")
    async def menu_buy(callback: CallbackQuery, state: FSMContext) -> None:
        msg = callback_message(callback)
        if msg is None:
            await callback.answer()
            return
        await callback.answer()
        await state.clear()
        await state.update_data(side="buy")
        await send_screen(msg, assets_dir, "🪐 Выбери планету с твоей монетой", "buy_coin", kb_buy_coins())

    @router.callback_query(F.data.startswith("buy:coin:"))
    async def buy_coin(callback: CallbackQuery, state: FSMContext) -> None:
        msg = callback_message(callback)
        if msg is None:
            await callback.answer()
            return
        await callback.answer()
        coin_key = (callback.data or "").split(":")[-1]
        if coin_key not in COINS:
            return
        await state.update_data(side="buy", coin=coin_key)
        await send_screen(
            msg,
            assets_dir,
            "🚀 Запускаем платёжный модуль, выбери способ оплаты",
            "buy_method",
            kb_buy_method(ctx.settings),
        )

    @router.callback_query(F.data.startswith("buy:method:"))
    async def buy_method(callback: CallbackQuery, state: FSMContext) -> None:
        msg = callback_message(callback)
        if msg is None:
            await callback.answer()
            return
        await callback.answer()
        raw_index = (callback.data or "").split(":")[-1]
        methods = ctx.settings.payment_methods()
        if raw_index.isdigit():
            method_index = int(raw_index)
        else:
            # Backward compatibility for old callback payloads like buy:method:card_ru
            method_index = 0
        if method_index < 0 or method_index >= len(methods):
            return
        data = await state.get_data()
        coin_key = data.get("coin", "btc")
        coin_title = COINS[coin_key]["title"]
        await state.update_data(pay_method=methods[method_index])
        await state.set_state(TradeState.waiting_buy_amount)
        await send_screen(
            msg,
            assets_dir,
            (
                f"Введите нужную сумму в {coin_title} или в рублях (RUB) \n\n"
                "Пример: 0.00012 или 0,00012 или 5000\n\n"
                "⚠️ Внимание: из-за разницы курсов на различных платформах, "
                "рекомендуем указывать сумму в криптовалюте!"
            ),
            "buy_amount",
            kb_cancel(),
        )

    @router.message(TradeState.waiting_buy_amount)
    async def buy_amount(message: Message, state: FSMContext) -> None:
        amount = parse_amount(message.text or "")
        if amount is None:
            await message.answer("Не понял сумму. Отправьте число, например: 5000 или 0.00012")
            return

        data = await state.get_data()
        coin_key = str(data.get("coin", "btc"))
        if coin_key not in COINS:
            coin_key = "btc"
        mode = detect_mode(message.text or "", amount)
        current_rates = await ctx.rates.get_rates()
        rate = float(current_rates.get(coin_key, 0.0))
        if rate <= 0:
            await message.answer("Не удалось получить курс. Попробуйте ещё раз через несколько секунд.")
            return
        quote = calc_quote("buy", amount, mode, rate, ctx.settings.commission_percent)
        if float(quote["amount_rub"]) < min_buy_rub:
            await message.answer("Минимальная сумма обмена: 1500 RUB")
            return
        await state.update_data(quote=quote, mode=mode)

        symbol = COINS[coin_key]["symbol"]
        market_rub = round(float(quote["amount_coin"]) * float(quote["rate"]))
        text = (
            "🚀 Платёжные данные:\n\n"
            f"Средний рыночный курс: {fmt_plain(float(quote['rate']))} RUB\n"
            "<i>Курс не учитывает комиссию сервиса!</i>\n\n"
            f"Вы получите: {fmt_coin(quote['amount_coin'])} {symbol} (~ {market_rub} RUB)\n\n"
            "🔄 Внутренний баланс кошелька: 0 RUB\n\n"
            f"📌 К оплате {fmt_plain(float(quote['amount_rub']))} RUB 📌\n\n"
            "⚠️ <b>Важно:</b> <i>Отправляйте средства только со своей личной карты или подручных "
            "счетов, администрация может запросить верификацию платежа или задержать обмен для "
            "проверки дополнительных данных.</i>"
        )
        await send_screen(message, assets_dir, text, "buy_method", kb_buy_confirm())

    @router.callback_query(F.data == "buy:wallet_balance")
    async def buy_wallet_balance(callback: CallbackQuery) -> None:
        await callback.answer("Внутренний баланс кошелька: 0 RUB", show_alert=True)

    @router.callback_query(F.data == "buy:paid")
    async def buy_paid(callback: CallbackQuery) -> None:
        msg = callback_message(callback)
        await callback.answer("Платёж отмечен. Передаём оператору.", show_alert=True)
        if msg is None:
            return
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="👽 Оператор", url=ctx.settings.link("operator"))],
                [InlineKeyboardButton(text="🏠 В меню", callback_data="nav:main")],
            ]
        )
        await msg.answer("✅ Платёж отправлен. Ожидайте проверку оператора.", reply_markup=kb)

    @router.callback_query(F.data == "buy:confirm")
    async def buy_confirm(callback: CallbackQuery, state: FSMContext) -> None:
        msg = callback_message(callback)
        if msg is None:
            await callback.answer()
            return
        await callback.answer()
        data = await state.get_data()
        coin_key = data.get("coin", "btc")
        if "quote" not in data:
            await state.clear()
            await msg.answer("Сессия устарела. Нажмите /start и начните обмен заново.")
            return
        title = COINS[coin_key]["title"]
        await state.set_state(TradeState.waiting_buy_wallet)
        await send_screen(msg, assets_dir, f"Укажи {title}-Кошелек:", "wallet", kb_cancel())

    @router.message(TradeState.waiting_buy_wallet)
    async def buy_wallet(message: Message, state: FSMContext) -> None:
        wallet = (message.text or "").strip()
        if len(wallet) < 12:
            await message.answer("Кошелёк выглядит слишком коротким, пришлите корректный адрес.")
            return
        user_id = message_user_id(message)
        if user_id is None:
            await message.answer("Не удалось определить пользователя, попробуйте ещё раз.")
            return

        data = await state.get_data()
        if "quote" not in data:
            await state.clear()
            await message.answer("Сессия устарела. Нажмите /start и начните обмен заново.")
            return
        coin_key = data.get("coin", "btc")
        symbol = COINS[coin_key]["symbol"]
        quote = data["quote"]
        order_id = random.randint(ctx.settings.min_rub00, 999999)
        requisites_value = ctx.settings.requisites_value.strip()
        card_number = format_card_like(requisites_value)

        ctx.users.record_trade(
            user_id=user_id,
            side="buy",
            coin=symbol,
            amount_coin=float(quote["amount_coin"]),
            amount_rub=float(quote["amount_rub"]),
        )
        await state.clear()

        if not requisites_value:
            await message.answer("❌Нет свободных реквизитов. ⚠ Попробуйте выбрать другой метод оплаты или попробуйте позже ➡️ /start")
            return

        text = (
            "⭕ ВРЕМЯ НА ОПЛАТУ 15 МИНУТ, ЕСЛИ НЕ УСПЕВАЕТЕ ОПЛАТИТЬ, ЛУЧШЕ СОЗДАЙТЕ НОВУЮ ЗАЯВКУ ⭕\n\n"
            f"🔷 Номер заявки {order_id}\n"
            f"🔷 Банк-получатель: {ctx.settings.requisites_bank}\n"
            f"🔷 Номер карты: {card_number}\n"
            f"🔷 Сумма к оплате: {fmt_plain(float(quote['amount_rub']))} RUB\n\n"
            f"Сумма покупки: {fmt_coin(quote['amount_coin'])} {symbol}\n"
            f"Кошелек получателя:\n{wallet}\n\n"
            "⚠️ <b>Внимание:</b> <i>средства, отправленные не на тот банк, возврату не подлежат! "
            "Оплачивать вы должны ровно ту сумму, которая указана в заявке, иначе мы ваш платеж "
            "не найдем! Все претензии по обмену принимаются в течении 24 часов.</i>"
        )
        await send_screen(message, assets_dir, text, "buy_requisites", kb_buy_order_actions())

    return router
