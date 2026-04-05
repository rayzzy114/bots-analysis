from pathlib import Path

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from ..context import AppContext
from ..keyboards import kb_sell_operator
from ..media import send_screen
from ..telegram_helpers import callback_message


def build_sell_router(_ctx: AppContext, assets_dir: Path) -> Router:
    router = Router(name="sell")

    @router.callback_query(F.data == "menu:sell")
    async def menu_sell(callback: CallbackQuery, state: FSMContext) -> None:
        msg = callback_message(callback)
        if msg is None:
            await callback.answer()
            return
        await callback.answer()
        await state.clear()
        await send_screen(
            msg,
            assets_dir,
            "👽 Продай монеты через нашего оператора",
            "sell",
            kb_sell_operator(),
        )

    return router
