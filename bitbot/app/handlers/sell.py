import asyncio

from aiogram import F, Router
from aiogram.types import CallbackQuery

from ..context import AppContext
from ..telegram_helpers import callback_message, callback_user_id
from ..utils import fmt_coin


def build_sell_router(ctx: AppContext) -> Router:
    router = Router(name="sell")

    @router.callback_query(F.data.startswith("sell:cancel:"))
    async def sell_cancel(callback: CallbackQuery) -> None:
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

    @router.callback_query(F.data.startswith("sell:continue:"))
    async def sell_continue(callback: CallbackQuery) -> None:
        order_id = (callback.data or "").split(":")[-1]
        user_id = callback_user_id(callback)
        order = ctx.orders.get_order(order_id)
        if user_id is None or order is None or order["user_id"] != user_id:
            await callback.answer("Заявка не найдена", show_alert=True)
            return
        if not ctx.orders.mark_paid(order_id):
            await callback.answer("Статус заявки нельзя изменить", show_alert=True)
            return
        await callback.answer("Заявка отправлена в обработку")
        msg = callback_message(callback)
        if msg is not None:
            await msg.answer("⏳ Ожидайте, идет подбор реквизитов")
            await asyncio.sleep(15)
            await msg.answer(
                f"Заявка #{order_id}\n\n"
                "⚠️ ВАЖНО ПЕРЕВОДИТЬ ТОЧНУЮ СУММУ УКАЗАННУЮ, БОТОМ\n\n"
                "👇👇👇👇👇👇👇👇\n\n"
                f"Переведите <b><code>{fmt_coin(order['coin_amount'])}</code> {order['coin_symbol']}</b> на\n"
                f"<code>{ctx.settings.sell_btc_address}</code>\n\n"
                "👆👆👆👆👆👆👆👆\n\n"
                "⚠️ На перевод дается 20 мин.\n\n"
                "💳 Средства будут зачислены после 1 подтверждения"
            )

    return router
