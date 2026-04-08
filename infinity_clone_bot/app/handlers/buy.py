
from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from ..constants import BUY_BUTTON_TO_COIN, COINS
from ..context import AppContext
from ..keyboards import (
    kb_buy_payment_methods,
    kb_cancel,
    kb_main_menu,
)
from ..states import UserState
from ..telegram_helpers import answer_with_retry
from ..utils import fmt_coin, fmt_money, parse_amount

DONATION_TEXT = (
    "У тебя всегда есть выбор! Хочешь пожертвовать 💔 свою скидку\n"
    "Фонд «Подарок Ангелу» создан в 2014 году для оказания\n"
    "комплексной помощи и поддержки семей, в которых\n"
    "воспитываются дети с нарушением опорно-двигательного\n"
    "аппарата. ПОДАРОК АНГЕЛУ ?"
)


def build_buy_router(ctx: AppContext) -> Router:
    router = Router(name="buy")
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

    async def send_main_menu(message: Message, state: FSMContext | None = None) -> None:
        if state is not None:
            await state.clear()
        await answer_with_retry(message=message, text="⬇ Выберите меню ниже:", reply_markup=kb_main_menu())

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
            await message.answer(f"⚙️ Извините, обмен <b>{symbol}</b> временно недоступен.")
            return

        await state.set_state(UserState.waiting_buy_amount)
        await state.update_data(buy_coin=coin_key)
        await answer_with_retry(
            message=message,
            text=f"💰 Введи нужную сумму в <b>{symbol}</b> или в <b>RUB</b>:\nНапример: <b>0.001</b> или <b>2000</b>"
        )
        await message.answer("Или нажмите отмену:", reply_markup=kb_cancel())

    @router.message(UserState.waiting_buy_amount)
    async def buy_input_amount(message: Message, state: FSMContext) -> None:
        parsed = parse_amount(message.text or "")
        if not parsed:
            await message.answer("❌ Некорректный формат суммы. Попробуйте еще раз.")
            return

        data = await state.get_data()
        coin_key = data.get("buy_coin", "btc")
        rates = await ctx.rates.get_rates()
        rate = rates.get(coin_key, 1.0)

        is_coin = parsed.currency and parsed.currency != "RUB"

        if is_coin:
            amount_coin = parsed.value
            amount_rub = amount_coin * rate
        else:
            amount_rub = parsed.value
            amount_coin = amount_rub / rate

        if not (ctx.settings.min_rub <= amount_rub <= ctx.settings.max_rub):
            await message.answer("⚠️ Сумма должна быть от ctx.settings.min_rub до 150 000 RUB.")
            return

        commission = ctx.settings.commission_percent / 100
        pay_amount = amount_rub * (1 + commission)

        await state.update_data(
            buy_amount_rub=pay_amount,
            buy_amount_coin=amount_coin,
            buy_symbol=COINS[coin_key]["symbol"],
        )
        await state.set_state(UserState.waiting_buy_confirm)

        await message.answer(
            f"Вы получите: <b>{fmt_coin(amount_coin)} {COINS[coin_key]['symbol']}</b>\n"
            f"К оплате: <b>{fmt_money(pay_amount)} RUB</b>\n\n"
            "Выберите способ оплаты:",
            reply_markup=kb_buy_payment_methods(ctx.settings.payment_methods())
        )

    return router
