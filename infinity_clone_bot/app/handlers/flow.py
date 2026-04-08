from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from ..constants import COINS
from ..context import AppContext
from ..states import UserState
from ..utils import fmt_coin, fmt_money, parse_amount


def build_flow_router(ctx: AppContext) -> Router:
    router = Router(name="flow")

    @router.message(UserState.waiting_calc_amount)
    async def calc_amount(message: Message, state: FSMContext) -> None:
        parsed = parse_amount(message.text or "")
        if not parsed:
            await message.answer("❌ Некорректная сумма.")
            return

        # Assume coin_key in data
        data = await state.get_data()
        coin_key = data.get("coin_key", "btc")
        rates = await ctx.rates.get_rates()
        rate = rates.get(coin_key, 1.0)

        commission = ctx.settings.commission_percent / 100
        is_coin = parsed.currency and parsed.currency != "RUB"

        if is_coin:
            amount_coin = parsed.value
            amount_rub = amount_coin * rate * (1 + commission)
        else:
            amount_rub = parsed.value
            amount_coin = amount_rub / (rate * (1 + commission))

        await message.answer(
            f"💰 Вы получите: <b>{fmt_coin(amount_coin)} {COINS[coin_key]['symbol']}</b>\n"
            f"💰 К получению: <b>{fmt_money(amount_rub)} RUB</b>"
        )
        await state.clear()

    return router
