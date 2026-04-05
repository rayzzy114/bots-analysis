from aiogram import Router

from ..context import AppContext


def build_buy_router(ctx: AppContext) -> Router:
    _ = ctx
    # AdminKit is admin-only; buy flow is implemented in the target bot.
    return Router(name="buy_adminkit_stub")
