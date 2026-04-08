from aiogram import Router

from handlers import (
    admin,
    buy_base,
    buy_btc,
    buy_xmr,
    cabinet,
    daily_bonus,
    faq,
    none,
    pay_with_,
    sell_btc_xmr,
    start,
    support,
)


def get_routers() -> list[Router]:
    return [
        start.router,
        admin.router,
        daily_bonus.router,
        support.router,
        faq.router,
        buy_btc.router,
        buy_xmr.router,
        cabinet.router,
        sell_btc_xmr.router,

        pay_with_.router,
        buy_base.router,

        none.router
    ]
